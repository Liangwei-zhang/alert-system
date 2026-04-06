from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.models.events import EventOutboxModel

DEAD_LETTER_STATUS = "dead_letter"


@dataclass(slots=True)
class OutboxEvent:
    topic: str
    payload: dict[str, Any]
    key: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _normalize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, dict):
        return {str(key): _normalize_value(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_normalize_value(item) for item in value]
    return value


def normalize_event(
    topic: str,
    payload: dict[str, Any],
    *,
    key: str | None = None,
    headers: dict[str, str] | None = None,
    occurred_at: datetime | None = None,
) -> OutboxEvent:
    return OutboxEvent(
        topic=topic,
        payload=_normalize_value(payload),
        key=key,
        headers=_normalize_value(headers or {}),
        occurred_at=occurred_at or datetime.now(timezone.utc),
    )


class OutboxPublisher:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def publish_after_commit(
        self,
        topic: str,
        payload: dict[str, Any],
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> OutboxEvent:
        event = normalize_event(topic, payload, key=key, headers=headers)
        self.session.add(
            EventOutboxModel(
                topic=event.topic,
                event_key=event.key,
                payload=event.payload,
                headers=event.headers,
                occurred_at=event.occurred_at,
            )
        )
        return event

    async def publish_batch_after_commit(
        self,
        events: Iterable[OutboxEvent],
    ) -> list[OutboxEvent]:
        normalized = [
            normalize_event(
                event.topic,
                event.payload,
                key=event.key,
                headers=event.headers,
                occurred_at=event.occurred_at,
            )
            for event in events
        ]
        self.session.add_all(
            [
                EventOutboxModel(
                    topic=event.topic,
                    event_key=event.key,
                    payload=event.payload,
                    headers=event.headers,
                    occurred_at=event.occurred_at,
                )
                for event in normalized
            ]
        )
        return normalized


class EventOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_audit_events(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        entity: str | None = None,
        entity_id: str | None = None,
        action: str | None = None,
        source: str | None = None,
        status: str | None = None,
        request_id: str | None = None,
    ) -> list[EventOutboxModel]:
        records = await self._load_audit_events(status=status)
        filtered = self._filter_audit_records(
            records,
            entity=entity,
            entity_id=entity_id,
            action=action,
            source=source,
            request_id=request_id,
        )
        return filtered[offset : offset + limit]

    async def count_audit_events(
        self,
        *,
        entity: str | None = None,
        entity_id: str | None = None,
        action: str | None = None,
        source: str | None = None,
        status: str | None = None,
        request_id: str | None = None,
    ) -> int:
        records = await self._load_audit_events(status=status)
        filtered = self._filter_audit_records(
            records,
            entity=entity,
            entity_id=entity_id,
            action=action,
            source=source,
            request_id=request_id,
        )
        return len(filtered)

    async def count_runtime_records(
        self,
        *,
        status: str | None = None,
        retried_only: bool = False,
    ) -> int:
        statement = select(func.count(EventOutboxModel.id))
        if status is not None:
            statement = statement.where(EventOutboxModel.status == status.strip().lower())
        if retried_only:
            statement = statement.where(EventOutboxModel.attempt_count > 0)
        result = await self.session.execute(statement)
        return int(result.scalar_one() or 0)

    async def claim_pending(self, limit: int = 100) -> list[EventOutboxModel]:
        result = await self.session.execute(
            select(EventOutboxModel)
            .where(EventOutboxModel.status == "pending")
            .order_by(EventOutboxModel.created_at.asc(), EventOutboxModel.id.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_published(
        self,
        record: EventOutboxModel,
        *,
        broker_message_id: str,
    ) -> EventOutboxModel:
        record.status = "published"
        record.broker_message_id = broker_message_id
        record.published_at = datetime.now(timezone.utc)
        record.last_error = None
        await self.session.flush()
        return record

    async def mark_dead_letter(
        self,
        record: EventOutboxModel,
        *,
        error_message: str,
    ) -> EventOutboxModel:
        record.status = DEAD_LETTER_STATUS
        record.attempt_count = int(record.attempt_count or 0) + 1
        record.last_error = error_message
        await self.session.flush()
        return record

    async def requeue(
        self,
        record: EventOutboxModel,
        *,
        error_message: str,
    ) -> EventOutboxModel:
        record.status = "pending"
        record.attempt_count = int(record.attempt_count or 0) + 1
        record.last_error = error_message
        await self.session.flush()
        return record

    async def delete_published(
        self,
        *,
        retention_days: int,
        limit: int = 1000,
    ) -> int:
        if retention_days <= 0 or limit <= 0:
            return 0

        from sqlalchemy import delete, select

        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        result = await self.session.execute(
            select(EventOutboxModel.id)
            .where(
                EventOutboxModel.status == "published",
                EventOutboxModel.published_at.is_not(None),
                EventOutboxModel.published_at < cutoff,
            )
            .order_by(EventOutboxModel.published_at.asc(), EventOutboxModel.id.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        record_ids = [str(record_id) for record_id in result.scalars().all()]
        if not record_ids:
            return 0

        await self.session.execute(
            delete(EventOutboxModel).where(EventOutboxModel.id.in_(record_ids))
        )
        await self.session.flush()
        return len(record_ids)

    async def list_dead_letter(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EventOutboxModel]:
        result = await self.session.execute(
            select(EventOutboxModel)
            .where(EventOutboxModel.status == DEAD_LETTER_STATUS)
            .order_by(EventOutboxModel.created_at.asc(), EventOutboxModel.id.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def replay_dead_letter(
        self,
        *,
        limit: int = 100,
        record_ids: Iterable[str] | None = None,
    ) -> list[EventOutboxModel]:
        normalized_ids = [
            str(record_id).strip() for record_id in (record_ids or []) if str(record_id).strip()
        ]
        statement = (
            select(EventOutboxModel)
            .where(EventOutboxModel.status == DEAD_LETTER_STATUS)
            .order_by(EventOutboxModel.created_at.asc(), EventOutboxModel.id.asc())
            .with_for_update(skip_locked=True)
        )
        if normalized_ids:
            statement = statement.where(EventOutboxModel.id.in_(normalized_ids))
        else:
            statement = statement.limit(limit)

        result = await self.session.execute(statement)
        records = list(result.scalars().all())
        for record in records:
            record.status = "pending"
            record.last_error = None
        await self.session.flush()
        return records

    async def _load_audit_events(self, *, status: str | None = None) -> list[EventOutboxModel]:
        statement = select(EventOutboxModel).where(EventOutboxModel.topic == "ops.audit.logged")
        if status:
            statement = statement.where(EventOutboxModel.status == status.strip().lower())
        result = await self.session.execute(
            statement.order_by(EventOutboxModel.created_at.desc(), EventOutboxModel.id.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    def _filter_audit_records(
        records: list[EventOutboxModel],
        *,
        entity: str | None = None,
        entity_id: str | None = None,
        action: str | None = None,
        source: str | None = None,
        request_id: str | None = None,
    ) -> list[EventOutboxModel]:
        filtered: list[EventOutboxModel] = []
        for record in records:
            payload = dict(record.payload or {})
            headers = dict(record.headers or {})
            if entity and str(payload.get("entity") or "") != entity:
                continue
            if entity_id and str(payload.get("entity_id") or "") != entity_id:
                continue
            if action and str(payload.get("action") or "") != action:
                continue
            if source and str(payload.get("source") or "") != source:
                continue
            if (
                request_id
                and str(headers.get("request_id") or payload.get("request_id") or "") != request_id
            ):
                continue
            filtered.append(record)
        return filtered


def event_from_record(record: EventOutboxModel) -> OutboxEvent:
    return OutboxEvent(
        topic=record.topic,
        payload=dict(record.payload or {}),
        key=record.event_key,
        headers={str(key): str(value) for key, value in dict(record.headers or {}).items()},
        occurred_at=record.occurred_at,
    )


def pop_pending_events(session: AsyncSession) -> list[OutboxEvent]:
    del session
    return []


async def _run_cli(args: argparse.Namespace) -> int:
    from infra.db.session import get_session_factory

    session_factory = get_session_factory()
    async with session_factory() as session:
        repository = EventOutboxRepository(session)

        if args.subcommand == "stats":
            payload = {
                "pending": await repository.count_runtime_records(status="pending"),
                "published": await repository.count_runtime_records(status="published"),
                "dead_letter": await repository.count_runtime_records(status=DEAD_LETTER_STATUS),
                "retried_pending": await repository.count_runtime_records(
                    status="pending",
                    retried_only=True,
                ),
            }
            if args.format == "json":
                print(json.dumps(payload, indent=2, sort_keys=True))
            else:
                for key, value in payload.items():
                    print(f"{key}={value}")
            return 0

        record_ids = None
        if args.ids:
            record_ids = [item.strip() for item in args.ids.split(",") if item.strip()]
        records = await repository.replay_dead_letter(limit=args.limit, record_ids=record_ids)
        await session.commit()
        payload = {
            "replayed": len(records),
            "record_ids": [str(record.id) for record in records],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect and replay event outbox dead-letter records."
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    stats_parser = subparsers.add_parser("stats", help="Print event outbox runtime counters.")
    stats_parser.add_argument("--format", choices=("json", "env"), default="json")

    replay_parser = subparsers.add_parser(
        "replay-dead-letter",
        help="Move dead-lettered records back to pending for replay.",
    )
    replay_parser.add_argument("--limit", type=int, default=100)
    replay_parser.add_argument(
        "--ids",
        default="",
        help="Comma-separated event_outbox ids to replay. When omitted, replays the oldest dead-letter records up to --limit.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_run_cli(args))


if __name__ == "__main__":
    raise SystemExit(main())
