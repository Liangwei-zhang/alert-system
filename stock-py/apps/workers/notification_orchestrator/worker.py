from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Sequence

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
    def __init__(self, default_channels: Sequence[str] = ("push", "email")) -> None:
        self.default_channels = tuple(default_channels)

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
        prepared = self.normalize_event(topic, payload)
        if not prepared:
            logger.info("Skipped topic=%s because no recipient could be resolved", topic)
            return {"created": 0, "requested": 0}

        from domains.notifications.repository import (
            MessageOutboxRepository,
            NotificationRepository,
            ReceiptRepository,
        )
        from infra.db.session import get_session_factory
        from infra.events.outbox import OutboxPublisher

        session_factory = get_session_factory()

        async with session_factory() as session:
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

                if outbox_rows:
                    outbox_items = await outbox_repository.bulk_create(outbox_rows)
                    for outbox_item in outbox_items:
                        requested += 1
                        await publisher.publish_after_commit(
                            topic="notification.requested",
                            key=outbox_item.id,
                            payload={
                                "outbox_id": outbox_item.id,
                                "notification_id": notification.id,
                                "user_id": notification.user_id,
                                "channel": outbox_item.channel,
                            },
                        )
            await session.commit()

        return {"created": len(notifications), "requested": requested}

    def normalize_event(self, topic: str, payload: dict[str, Any]) -> list[PreparedNotification]:
        if topic == "signal.generated":
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
            "buy": f"Buy signal: {symbol}",
            "sell": f"Sell signal: {symbol}",
            "split_buy": f"Split buy signal: {symbol}",
            "split_sell": f"Split sell signal: {symbol}",
        }
        body_map = {
            "buy": self._signal_body(symbol, price, "Buy opportunity detected."),
            "sell": self._signal_body(symbol, price, "Sell opportunity detected."),
            "split_buy": self._signal_body(symbol, price, "Scaled buy opportunity detected."),
            "split_sell": self._signal_body(symbol, price, "Scaled sell opportunity detected."),
        }

        title = title_map.get(signal_type, f"Signal generated: {symbol}")
        body = body_map.get(
            signal_type, self._signal_body(symbol, price, "A new signal is available.")
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
        decision_summary = str(
            self._first_value(
                payload.get("decision_summary"),
                result_payload.get("decision_summary"),
                f"TradingAgents finished with action {final_action}.",
            )
        )

        if status != "completed":
            title = f"AI analysis {status}: {symbol}"
        elif final_action in {"buy", "sell", "add"}:
            title = f"AI suggests {final_action}: {symbol}"
        else:
            title = f"AI analysis completed: {symbol}"

        metadata = {
            "request_id": payload.get("request_id"),
            "job_id": payload.get("job_id"),
            "status": status,
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
            return f"{fallback} Symbol: {symbol}."
        return f"{fallback} Symbol: {symbol}. Entry price: {price}."

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
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
        return int(value)

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
