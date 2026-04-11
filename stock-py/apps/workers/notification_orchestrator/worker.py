from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Iterator, Sequence

from domains.signals.audience_service import SignalAudienceResolver
from infra.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PreparedNotification:
    user_id: int
    type: str
    title: str
    body: str
    signal_id: str | None = None
    trade_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    ack_required: bool = False
    ack_deadline_at: datetime | None = None
    channels: list[str] = field(default_factory=list)


class NotificationOrchestratorWorker:
    def __init__(
        self,
        default_channels: Sequence[str] = ("push", "email"),
        *,
        fanout_batch_size: int | None = None,
        push_dispatch_batch_size: int | None = None,
    ) -> None:
        settings = get_settings()
        self.default_channels = tuple(default_channels)
        self.fanout_batch_size = max(
            int(fanout_batch_size or settings.notification_fanout_batch_size),
            1,
        )
        self.push_dispatch_batch_size = max(
            int(push_dispatch_batch_size or settings.push_dispatch_batch_size),
            1,
        )

    async def process_events(
        self,
        events: Iterable[tuple[str, dict[str, Any]]],
    ) -> dict[str, int]:
        stats = {"events": 0, "created": 0, "requested": 0}
        for topic, payload in events:
            result = await self.process_event(topic, payload)
            stats["events"] += 1
            stats["created"] += result["created"]
            stats["requested"] += result["requested"]
        return stats

    async def process_event(self, topic: str, payload: dict[str, Any]) -> dict[str, int]:
        if topic == "signal.generated" and not self._has_recipients(payload):
            return await self._fanout_signal_generated(payload)

        prepared = self.normalize_event(topic, payload)
        if not prepared:
            logger.info("Skipped topic=%s because no recipient could be resolved", topic)
            return {"created": 0, "requested": 0}

        from infra.db.session import get_session_factory

        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await self._save_prepared_notifications(prepared, session)
            await session.commit()
            return result

    async def _fanout_signal_generated(self, payload: dict[str, Any]) -> dict[str, int]:
        from infra.db.session import get_session_factory
        from infra.events.outbox import OutboxPublisher

        symbol = str(payload.get("symbol") or "").strip().upper()
        if not symbol:
            logger.info("Skipped signal fan-out because symbol is missing")
            return {"created": 0, "requested": 0}

        signal_id = self._string_or_none(payload.get("signal_id"))
        try:
            score = float(payload.get("score") or 0)
        except (TypeError, ValueError):
            score = 0.0

        batches = 0
        recipients = 0
        session_factory = get_session_factory()
        async with session_factory() as session:
            audience = SignalAudienceResolver(session)
            publisher = OutboxPublisher(session)

            async for user_ids in audience.iter_recipient_batches(
                symbol,
                score,
                batch_size=self.fanout_batch_size,
            ):
                batches += 1
                recipients += len(user_ids)
                await publisher.publish_after_commit(
                    topic="notification.batch.requested",
                    key=f"{signal_id}:{batches}" if signal_id else str(batches),
                    payload=self._build_batch_payload(payload, user_ids, batch_no=batches),
                )
                await session.commit()

        logger.info(
            "Signal fan-out finished signal_id=%s symbol=%s batches=%s recipients=%s",
            signal_id,
            symbol,
            batches,
            recipients,
        )
        return {"created": 0, "requested": 0}

    async def _save_prepared_notifications(
        self,
        prepared: list[PreparedNotification],
        session: Any,
    ) -> dict[str, int]:
        from domains.notifications.repository import (
            MessageOutboxRepository,
            NotificationRepository,
            ReceiptRepository,
        )
        from infra.events.outbox import OutboxPublisher

        notification_repository = NotificationRepository(session)
        receipt_repository = ReceiptRepository(session)
        outbox_repository = MessageOutboxRepository(session)
        publisher = OutboxPublisher(session)

        notifications = await notification_repository.bulk_create(
            [
                {
                    "user_id": item.user_id,
                    "signal_id": item.signal_id,
                    "trade_id": item.trade_id,
                    "type": item.type,
                    "title": item.title,
                    "body": item.body,
                    "metadata": item.metadata or None,
                }
                for item in prepared
            ]
        )

        requested = 0
        push_outbox_ids: list[str] = []

        for item, notification in zip(prepared, notifications):
            receipt = await receipt_repository.create_receipt(
                notification_id=notification.id,
                user_id=notification.user_id,
                ack_required=item.ack_required,
                ack_deadline_at=item.ack_deadline_at,
            )

            outbox_rows = [
                {
                    "notification_id": notification.id,
                    "user_id": notification.user_id,
                    "channel": channel,
                    "payload": {
                        "title": notification.title,
                        "body": notification.body,
                        "subject": notification.title,
                        "notification_type": notification.type,
                        "signal_id": notification.signal_id,
                        "trade_id": notification.trade_id,
                        "receipt_id": receipt.id,
                        "metadata": item.metadata or {},
                        "url": "/app/notifications",
                        "tag": f"notification-{notification.id}",
                    },
                }
                for channel in item.channels
            ]

            if not outbox_rows:
                continue

            outbox_items = await outbox_repository.bulk_create(outbox_rows)
            for outbox_item in outbox_items:
                requested += 1
                if outbox_item.channel == "push":
                    push_outbox_ids.append(outbox_item.id)

        for outbox_ids in self._chunked(push_outbox_ids, self.push_dispatch_batch_size):
            await publisher.publish_after_commit(
                topic="notification.push.batch.requested",
                key=outbox_ids[0],
                payload={
                    "channel": "push",
                    "outbox_ids": outbox_ids,
                    "batch_size": len(outbox_ids),
                },
            )

        return {"created": len(notifications), "requested": requested}

    def normalize_event(self, topic: str, payload: dict[str, Any]) -> list[PreparedNotification]:
        if topic in {"signal.generated", "notification.batch.requested"}:
            return self._normalize_signal_generated(payload)
        if topic == "tradingagents.terminal":
            return self._normalize_tradingagents_terminal(payload)
        raise ValueError(f"Unsupported notification topic: {topic}")

    def _normalize_signal_generated(self, payload: dict[str, Any]) -> list[PreparedNotification]:
        signal = payload.get("signal") if isinstance(payload.get("signal"), dict) else {}
        symbol = str(
            self._first_value(
                payload.get("symbol"),
                payload.get("ticker"),
                signal.get("symbol"),
                "UNKNOWN",
            )
        ).upper()
        signal_type = str(
            self._first_value(
                payload.get("signal_type"),
                payload.get("action"),
                signal.get("signal_type"),
                "signal",
            )
        ).lower()
        price = self._first_value(
            payload.get("price"),
            payload.get("entry_price"),
            signal.get("entry_price"),
        )

        title_map = {
            "buy": f"买入信号：{symbol}",
            "sell": f"卖出信号：{symbol}",
            "split_buy": f"分批买入信号：{symbol}",
            "split_sell": f"分批卖出信号：{symbol}",
        }
        body_map = {
            "buy": self._signal_body(symbol, price, "检测到买入机会。"),
            "sell": self._signal_body(symbol, price, "检测到卖出机会。"),
            "split_buy": self._signal_body(symbol, price, "检测到分批买入机会。"),
            "split_sell": self._signal_body(
                symbol,
                price,
                "检测到分批卖出机会。",
            ),
        }

        title = title_map.get(signal_type, f"信号触发：{symbol}")
        body = body_map.get(
            signal_type,
            self._signal_body(symbol, price, "检测到新的交易信号。"),
        )
        metadata = {
            "symbol": symbol,
            "signal_type": signal_type,
            "price": price,
        }
        signal_id = self._string_or_none(payload.get("signal_id") or signal.get("id"))
        channels = self._normalize_channels(payload.get("channels"))
        ack_deadline_at = self._parse_datetime(payload.get("ack_deadline_at"))
        ack_required = bool(payload.get("ack_required", False))

        return [
            PreparedNotification(
                user_id=user_id,
                type="signal.generated",
                title=title,
                body=body,
                signal_id=signal_id,
                metadata=metadata,
                ack_required=ack_required,
                ack_deadline_at=ack_deadline_at,
                channels=channels,
            )
            for user_id in self._normalize_user_ids(payload)
        ]

    def _normalize_tradingagents_terminal(
        self,
        payload: dict[str, Any],
    ) -> list[PreparedNotification]:
        result_payload = (
            payload.get("result_payload") if isinstance(payload.get("result_payload"), dict) else {}
        )
        symbol = str(
            self._first_value(
                payload.get("symbol"),
                payload.get("ticker"),
                result_payload.get("symbol"),
                result_payload.get("ticker"),
                "UNKNOWN",
            )
        ).upper()
        final_action = str(
            self._first_value(
                payload.get("final_action"),
                result_payload.get("final_action"),
                "completed",
            )
        ).lower()
        status = str(self._first_value(payload.get("status"), "completed")).lower()
        normalized_status = "completed" if status == "succeeded" else status
        decision_summary = str(
            self._first_value(
                payload.get("decision_summary"),
                result_payload.get("decision_summary"),
                f"TradingAgents 分析已完成，建议动作：{self._action_label(final_action)}。",
            )
        )

        if normalized_status != "completed":
            title = f"AI 分析{self._status_label(normalized_status)}：{symbol}"
        elif final_action in {"buy", "sell", "add"}:
            title = f"AI 建议{self._action_label(final_action)}：{symbol}"
        else:
            title = f"AI 分析完成：{symbol}"

        metadata = {
            "request_id": payload.get("request_id"),
            "job_id": payload.get("job_id"),
            "status": normalized_status,
            "final_action": final_action,
        }
        channels = self._normalize_channels(payload.get("channels"))
        ack_deadline_at = self._parse_datetime(payload.get("ack_deadline_at"))
        ack_required = bool(payload.get("ack_required", final_action in {"buy", "sell", "add"}))

        return [
            PreparedNotification(
                user_id=user_id,
                type="tradingagents.terminal",
                title=title,
                body=decision_summary,
                trade_id=self._string_or_none(payload.get("trade_id")),
                metadata=metadata,
                ack_required=ack_required,
                ack_deadline_at=ack_deadline_at,
                channels=channels,
            )
            for user_id in self._normalize_user_ids(payload)
        ]

    @staticmethod
    def _chunked(values: Sequence[str], chunk_size: int) -> Iterator[list[str]]:
        for start in range(0, len(values), chunk_size):
            yield list(values[start : start + chunk_size])

    @staticmethod
    def _has_recipients(payload: dict[str, Any]) -> bool:
        if payload.get("user_ids"):
            return True
        if payload.get("recipients"):
            return True
        if payload.get("users"):
            return True
        return payload.get("user_id") not in (None, "")

    def _build_batch_payload(
        self,
        payload: dict[str, Any],
        user_ids: list[int],
        *,
        batch_no: int,
    ) -> dict[str, Any]:
        return {
            "signal_id": self._string_or_none(payload.get("signal_id")),
            "symbol": payload.get("symbol"),
            "signal_type": payload.get("signal_type"),
            "price": payload.get("price"),
            "channels": payload.get("channels"),
            "ack_required": payload.get("ack_required"),
            "ack_deadline_at": payload.get("ack_deadline_at"),
            "dedupe_key": payload.get("dedupe_key"),
            "user_ids": user_ids,
            "fanout_batch_no": batch_no,
            "fanout_batch_size": len(user_ids),
        }

    def _normalize_user_ids(self, payload: dict[str, Any]) -> list[int]:
        user_ids: list[int] = []

        for value in payload.get("user_ids") or []:
            normalized = self._coerce_user_id(value)
            if normalized is not None:
                user_ids.append(normalized)

        for container_key in ("recipients", "users"):
            for value in payload.get(container_key) or []:
                if isinstance(value, dict):
                    normalized = self._coerce_user_id(value.get("user_id", value.get("id")))
                else:
                    normalized = self._coerce_user_id(value)
                if normalized is not None:
                    user_ids.append(normalized)

        direct_user_id = self._coerce_user_id(payload.get("user_id"))
        if direct_user_id is not None:
            user_ids.append(direct_user_id)

        unique_user_ids: list[int] = []
        seen: set[int] = set()
        for user_id in user_ids:
            if user_id not in seen:
                seen.add(user_id)
                unique_user_ids.append(user_id)
        return unique_user_ids

    def _normalize_channels(self, raw_channels: Any) -> list[str]:
        candidates = (
            raw_channels if isinstance(raw_channels, (list, tuple, set)) else self.default_channels
        )
        normalized: list[str] = []
        seen: set[str] = set()
        for value in candidates:
            channel = str(value).strip().lower()
            if channel not in {"push", "email"}:
                continue
            if channel in seen:
                continue
            seen.add(channel)
            normalized.append(channel)
        return normalized

    @staticmethod
    def _signal_body(symbol: str, price: Any, fallback: str) -> str:
        if price in (None, ""):
            return f"{fallback} 标的：{symbol}。"
        return f"{fallback} 标的：{symbol}，入场价：{price}。"

    @staticmethod
    def _action_label(action: str) -> str:
        mapping = {
            "buy": "买入",
            "sell": "卖出",
            "add": "加仓",
            "reduce": "减仓",
            "hold": "观望",
            "completed": "已完成",
        }
        normalized = str(action or "").strip().lower()
        return mapping.get(normalized, normalized or "未知动作")

    @staticmethod
    def _status_label(status: str) -> str:
        mapping = {
            "queued": "排队中",
            "completed": "完成",
            "succeeded": "完成",
            "running": "进行中",
            "pending": "待执行",
            "failed": "失败",
            "error": "异常",
            "canceled": "已取消",
            "cancelled": "已取消",
        }
        normalized = str(status or "").strip().lower()
        return mapping.get(normalized, normalized or "未知状态")

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    @staticmethod
    def _first_value(*values: Any) -> Any:
        for value in values:
            if value not in (None, "", [], {}):
                return value
        return None

    @staticmethod
    def _coerce_user_id(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _string_or_none(value: Any) -> str | None:
        if value in (None, ""):
            return None
        return str(value)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Notification orchestrator worker is ready to process mapped events.")


if __name__ == "__main__":
    asyncio.run(main())
