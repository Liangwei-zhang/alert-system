from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import Any

from domains.analytics.sinks.notification_sink import NotificationAnalyticsSink
from domains.analytics.sinks.signal_sink import SignalAnalyticsSink
from domains.analytics.sinks.tradingagents_sink import TradingAgentsAnalyticsSink
from infra.analytics.clickhouse_client import ClickHouseClient, get_clickhouse_client
from infra.observability.metrics import get_metrics_registry

logger = logging.getLogger(__name__)


class AnalyticsSinkWorker:
    def __init__(self, client: ClickHouseClient | None = None) -> None:
        self.client = client or get_clickhouse_client()
        self.signal_sink = SignalAnalyticsSink(self.client)
        self.notification_sink = NotificationAnalyticsSink(self.client)
        self.tradingagents_sink = TradingAgentsAnalyticsSink(self.client)
        self.metrics = get_metrics_registry()
        self._running = False

    async def run_forever(self, event_source=None, poll_interval_seconds: int = 5) -> None:
        self._running = True
        while self._running:
            events = []
            if event_source is not None:
                maybe_batch = event_source()
                if hasattr(maybe_batch, "__await__"):
                    maybe_batch = await maybe_batch
                events = list(maybe_batch or [])
            if events:
                await self.process_events(events)
            await asyncio.sleep(poll_interval_seconds)

    async def process_events(self, events: Iterable[tuple[str, dict[str, Any]]]) -> dict[str, int]:
        stats = {"handled": 0, "ignored": 0, "failed": 0}
        for topic, payload in events:
            try:
                result = await self.handle_event(topic, payload)
            except Exception:
                logger.exception("Analytics sink failed for topic=%s", topic)
                self.metrics.counter(
                    "analytics_sink_failed_total", "Failed analytics sink events"
                ).inc()
                stats["failed"] += 1
                continue
            if result["handled"]:
                self.metrics.counter(
                    "analytics_sink_handled_total", "Handled analytics sink events"
                ).inc()
                stats["handled"] += 1
            else:
                stats["ignored"] += 1
        return stats

    async def handle_event(self, topic: str, payload: dict[str, Any]) -> dict[str, Any]:
        if topic == "signal.generated":
            row = await self.signal_sink.handle_signal_generated(payload)
            return {"handled": True, "table": "signal_events", "row": row}
        if topic == "scanner.decision.recorded":
            row = await self.signal_sink.handle_scanner_decision(payload)
            return {"handled": True, "table": "scanner_decision_events", "row": row}
        if topic == "strategy.rankings.refreshed":
            rows = await self.signal_sink.handle_strategy_rankings_refreshed(payload)
            return {"handled": True, "table": "strategy_health_events", "rows": len(rows)}
        if topic == "notification.requested":
            row = await self.notification_sink.handle_notification_requested(payload)
            return {"handled": True, "table": "notification_events", "row": row}
        if topic == "notification.delivered":
            row = await self.notification_sink.handle_notification_delivered(payload)
            return {"handled": True, "table": "notification_events", "row": row}
        if topic == "notification.acknowledged":
            row = await self.notification_sink.handle_notification_acknowledged(payload)
            return {"handled": True, "table": "receipt_events", "row": row}
        if topic == "trade.action.recorded":
            await self.client.insert_rows(
                "trade_events", [{"occurred_at": payload.get("occurred_at"), **payload}]
            )
            return {"handled": True, "table": "trade_events"}
        if topic == "account.subscription.started":
            await self.client.insert_rows(
                "subscription_events", [{"occurred_at": payload.get("occurred_at"), **payload}]
            )
            return {"handled": True, "table": "subscription_events"}
        if topic == "watchlist.changed":
            await self.client.insert_rows(
                "watchlist_events", [{"occurred_at": payload.get("occurred_at"), **payload}]
            )
            return {"handled": True, "table": "watchlist_events"}
        if topic == "portfolio.changed":
            await self.client.insert_rows(
                "portfolio_events", [{"occurred_at": payload.get("occurred_at"), **payload}]
            )
            return {"handled": True, "table": "portfolio_events"}
        if topic == "tradingagents.requested":
            row = await self.tradingagents_sink.handle_tradingagents_requested(payload)
            return {"handled": True, "table": "tradingagents_events", "row": row}
        if topic == "tradingagents.terminal":
            row = await self.tradingagents_sink.handle_tradingagents_terminal(payload)
            return {"handled": True, "table": "tradingagents_events", "row": row}
        return {"handled": False, "topic": topic}

    def stop(self) -> None:
        self._running = False


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Analytics sink worker initialized")


if __name__ == "__main__":
    asyncio.run(main())
