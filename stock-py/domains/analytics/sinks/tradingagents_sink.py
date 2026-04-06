from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from infra.analytics.clickhouse_client import ClickHouseClient


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TradingAgentsAnalyticsSink:
    def __init__(self, client: ClickHouseClient) -> None:
        self.client = client

    async def handle_tradingagents_requested(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = {
            "occurred_at": payload.get("occurred_at") or payload.get("requested_at") or utcnow(),
            "event_type": "requested",
            "request_id": payload.get("request_id"),
            "job_id": payload.get("job_id"),
            "ticker": str(payload.get("ticker") or "UNKNOWN").upper(),
            "trigger_type": payload.get("trigger_type") or "unknown",
            "status": payload.get("status") or "accepted",
        }
        await self.client.insert_rows("tradingagents_events", [row])
        return row

    async def handle_tradingagents_terminal(self, payload: dict[str, Any]) -> dict[str, Any]:
        submitted_at = self._parse_datetime(payload.get("submitted_at"))
        completed_at = self._parse_datetime(payload.get("completed_at")) or utcnow()
        latency_seconds = None
        if submitted_at is not None:
            latency_seconds = round((completed_at - submitted_at).total_seconds(), 4)
        row = {
            "occurred_at": payload.get("occurred_at") or completed_at,
            "event_type": "terminal",
            "request_id": payload.get("request_id"),
            "job_id": payload.get("job_id"),
            "ticker": str(payload.get("ticker") or "UNKNOWN").upper(),
            "status": payload.get("status") or "unknown",
            "final_action": payload.get("final_action") or "unknown",
            "latency_seconds": latency_seconds,
        }
        await self.client.insert_rows("tradingagents_events", [row])
        return row

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        if isinstance(value, str) and value.strip():
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        return None
