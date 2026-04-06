from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from infra.analytics.clickhouse_client import ClickHouseClient


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NotificationAnalyticsSink:
    def __init__(self, client: ClickHouseClient) -> None:
        self.client = client

    async def handle_notification_requested(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = {
            "occurred_at": payload.get("occurred_at") or utcnow(),
            "event_type": "requested",
            "outbox_id": payload.get("outbox_id"),
            "notification_id": payload.get("notification_id"),
            "user_id": payload.get("user_id"),
            "channel": payload.get("channel") or "unknown",
        }
        await self.client.insert_rows("notification_events", [row])
        return row

    async def handle_notification_delivered(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = {
            "occurred_at": payload.get("occurred_at") or utcnow(),
            "event_type": "delivered",
            "outbox_id": payload.get("outbox_id"),
            "notification_id": payload.get("notification_id"),
            "user_id": payload.get("user_id"),
            "channel": payload.get("channel") or "unknown",
        }
        await self.client.insert_rows("notification_events", [row])
        return row

    async def handle_notification_acknowledged(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = {
            "occurred_at": payload.get("occurred_at") or utcnow(),
            "event_type": "acknowledged",
            "notification_id": payload.get("notification_id"),
            "receipt_id": payload.get("receipt_id"),
            "user_id": payload.get("user_id"),
            "channel": payload.get("channel"),
        }
        await self.client.insert_rows("receipt_events", [row])
        return row
