from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.core.config import Settings, get_settings
from infra.db.models.events import EventOutboxModel
from infra.db.models.notifications import MessageReceiptArchiveModel, NotificationModel
from infra.storage.object_storage import ObjectStorageClient


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def month_start(value: datetime) -> datetime:
    normalized = (
        value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    )
    return normalized.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def next_month(value: datetime) -> datetime:
    current = month_start(value)
    if current.month == 12:
        return current.replace(year=current.year + 1, month=1)
    return current.replace(month=current.month + 1)


@dataclass(frozen=True, slots=True)
class PartitionArchiveSpec:
    table_name: str
    model: type
    timestamp_column: Any
    retention_days: int
    filters: tuple[Any, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class PartitionArchiveOutcome:
    partitions_archived: int = 0
    rows_pruned: int = 0
    manifests: list[dict[str, Any]] = field(default_factory=list)


class NotificationPartitionArchiveService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
        storage_client: ObjectStorageClient | None = None,
        max_partitions_per_table: int | None = None,
        notification_retention_days: int | None = None,
        receipt_archive_retention_days: int | None = None,
        event_outbox_retention_days: int | None = None,
    ) -> None:
        app_settings = settings or get_settings()
        self.session = session
        self.storage = storage_client or ObjectStorageClient()
        self.max_partitions_per_table = max(
            1,
            int(
                app_settings.retention_partition_archive_max_partitions_per_run
                if max_partitions_per_table is None
                else max_partitions_per_table
            ),
        )
        self.specs = (
            PartitionArchiveSpec(
                table_name="notifications",
                model=NotificationModel,
                timestamp_column=NotificationModel.created_at,
                retention_days=max(
                    1,
                    int(
                        app_settings.retention_notification_partition_retention_days
                        if notification_retention_days is None
                        else notification_retention_days
                    ),
                ),
            ),
            PartitionArchiveSpec(
                table_name="message_receipts_archive",
                model=MessageReceiptArchiveModel,
                timestamp_column=MessageReceiptArchiveModel.created_at,
                retention_days=max(
                    1,
                    int(
                        app_settings.retention_receipt_archive_partition_retention_days
                        if receipt_archive_retention_days is None
                        else receipt_archive_retention_days
                    ),
                ),
            ),
            PartitionArchiveSpec(
                table_name="event_outbox",
                model=EventOutboxModel,
                timestamp_column=EventOutboxModel.published_at,
                retention_days=max(
                    1,
                    int(
                        app_settings.retention_event_outbox_partition_retention_days
                        if event_outbox_retention_days is None
                        else event_outbox_retention_days
                    ),
                ),
                filters=(
                    EventOutboxModel.status == "published",
                    EventOutboxModel.published_at.is_not(None),
                ),
                metadata={"status": "published"},
            ),
        )

    async def archive_expired_partitions(self) -> PartitionArchiveOutcome:
        outcome = PartitionArchiveOutcome()
        for spec in self.specs:
            partitions = await self._list_eligible_partitions(spec)
            for partition_key in partitions[: self.max_partitions_per_table]:
                manifest = await self._archive_partition(spec, partition_key)
                if manifest is None:
                    continue
                outcome.partitions_archived += 1
                outcome.rows_pruned += int(manifest.get("row_count") or 0)
                outcome.manifests.append(manifest)
        return outcome

    async def _archive_partition(
        self,
        spec: PartitionArchiveSpec,
        partition_key: str,
    ) -> dict[str, Any] | None:
        start_at = datetime.strptime(partition_key, "%Y-%m").replace(tzinfo=timezone.utc)
        end_at = next_month(start_at)
        rows = await self._load_partition_rows(spec, start_at=start_at, end_at=end_at)
        if not rows:
            return None

        serialized_rows = [self._serialize_row(row) for row in rows]
        object_key = await self._upload_partition_rows(spec, partition_key, serialized_rows)
        manifest = {
            "table": spec.table_name,
            "partition_key": partition_key,
            "row_count": len(serialized_rows),
            "object_key": object_key,
            "exported_at": utcnow().isoformat(),
            "filters": dict(spec.metadata),
        }
        await self.storage.put_json(
            f"retention-archive/{spec.table_name}/{partition_key}/manifest.json",
            manifest,
        )
        await self._delete_partition_rows(spec, start_at=start_at, end_at=end_at)
        return manifest

    async def _upload_partition_rows(
        self,
        spec: PartitionArchiveSpec,
        partition_key: str,
        rows: list[dict[str, Any]],
    ) -> str:
        body = "\n".join(
            json.dumps(row, separators=(",", ":"), ensure_ascii=False, default=str) for row in rows
        )
        compressed = gzip.compress(body.encode("utf-8"))
        object_key = f"retention-archive/{spec.table_name}/{partition_key}/rows.jsonl.gz"
        await self.storage.put_bytes(object_key, compressed)
        return object_key

    async def _list_eligible_partitions(self, spec: PartitionArchiveSpec) -> list[str]:
        archive_before = month_start(utcnow() - timedelta(days=spec.retention_days))
        earliest_result = await self.session.execute(
            select(func.min(spec.timestamp_column)).where(
                spec.timestamp_column.is_not(None),
                spec.timestamp_column < archive_before,
                *spec.filters,
            )
        )
        earliest_timestamp = earliest_result.scalar_one_or_none()
        if earliest_timestamp is None:
            return []

        partitions: list[str] = []
        current = month_start(earliest_timestamp)
        while current < archive_before and len(partitions) < self.max_partitions_per_table:
            end_at = next_month(current)
            count_result = await self.session.execute(
                select(func.count())
                .select_from(spec.model)
                .where(
                    spec.timestamp_column >= current,
                    spec.timestamp_column < end_at,
                    *spec.filters,
                )
            )
            if int(count_result.scalar_one() or 0) > 0:
                partitions.append(current.strftime("%Y-%m"))
            current = end_at
        return partitions

    async def _load_partition_rows(
        self,
        spec: PartitionArchiveSpec,
        *,
        start_at: datetime,
        end_at: datetime,
    ) -> list[Any]:
        model_id = getattr(spec.model, "id", None)
        statement = select(spec.model).where(
            spec.timestamp_column >= start_at,
            spec.timestamp_column < end_at,
            *spec.filters,
        )
        if model_id is not None:
            statement = statement.order_by(spec.timestamp_column.asc(), model_id.asc())
        else:
            statement = statement.order_by(spec.timestamp_column.asc())
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def _delete_partition_rows(
        self,
        spec: PartitionArchiveSpec,
        *,
        start_at: datetime,
        end_at: datetime,
    ) -> int:
        result = await self.session.execute(
            delete(spec.model).where(
                spec.timestamp_column >= start_at,
                spec.timestamp_column < end_at,
                *spec.filters,
            )
        )
        await self.session.flush()
        return int(result.rowcount or 0)

    @classmethod
    def _serialize_row(cls, row: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            return {str(key): cls._normalize_value(value) for key, value in row.items()}

        payload: dict[str, Any] = {}
        for column in row.__table__.columns:
            payload[column.name] = cls._normalize_value(getattr(row, column.key))
        return payload

    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        if isinstance(value, datetime):
            normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return normalized.astimezone(timezone.utc).isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {str(key): cls._normalize_value(inner) for key, inner in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls._normalize_value(item) for item in value]
        return value
