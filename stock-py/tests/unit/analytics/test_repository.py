import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from domains.analytics.repository import AnalyticsRepository
from infra.analytics.clickhouse_client import ClickHouseClient


class AnalyticsRepositoryTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.client = ClickHouseClient(root_path=self.tempdir.name)
        self.repository = AnalyticsRepository(self.client)

    async def test_query_overview_distribution_and_tradingagents_metrics(self) -> None:
        now = datetime.now(timezone.utc)
        await self.client.insert_rows(
            "signal_events",
            [{"occurred_at": now, "signal_id": 1, "strategy": "momentum", "symbol": "AAPL"}],
        )
        await self.client.insert_rows(
            "scanner_decision_events",
            [{"occurred_at": now, "decision_id": 10, "decision": "emitted", "symbol": "AAPL"}],
        )
        await self.client.insert_rows(
            "notification_events",
            [
                {
                    "occurred_at": now,
                    "event_type": "requested",
                    "channel": "push",
                    "notification_id": 100,
                },
                {
                    "occurred_at": now,
                    "event_type": "delivered",
                    "channel": "push",
                    "notification_id": 100,
                },
                {
                    "occurred_at": now - timedelta(days=3),
                    "event_type": "requested",
                    "channel": "email",
                    "notification_id": 101,
                },
            ],
        )
        await self.client.insert_rows(
            "receipt_events",
            [
                {
                    "occurred_at": now,
                    "event_type": "acknowledged",
                    "notification_id": 100,
                    "receipt_id": 5,
                }
            ],
        )
        await self.client.insert_rows(
            "trade_events",
            [{"occurred_at": now, "trade_id": "T-1", "action": "buy"}],
        )
        await self.client.insert_rows(
            "subscription_events",
            [{"occurred_at": now, "user_id": 5, "plan_code": "pro"}],
        )
        await self.client.insert_rows(
            "tradingagents_events",
            [
                {
                    "occurred_at": now,
                    "event_type": "requested",
                    "request_id": "req-1",
                    "ticker": "AAPL",
                    "status": "accepted",
                },
                {
                    "occurred_at": now,
                    "event_type": "terminal",
                    "request_id": "req-1",
                    "ticker": "AAPL",
                    "status": "completed",
                    "final_action": "buy",
                    "latency_seconds": 12.5,
                },
            ],
        )

        overview = await self.repository.query_overview(24)
        distribution = await self.repository.query_distribution(24)
        tradingagents = await self.repository.query_tradingagents_metrics(24)

        self.assertEqual(overview["generated_signals"], 1)
        self.assertEqual(overview["scanner_decisions"], 1)
        self.assertEqual(overview["notification_requests"], 1)
        self.assertEqual(overview["delivered_notifications"], 1)
        self.assertEqual(overview["acknowledged_notifications"], 1)
        self.assertEqual(overview["trade_actions"], 1)
        self.assertEqual(overview["subscriptions_started"], 1)
        self.assertEqual(overview["tradingagents_terminals"], 1)
        self.assertIsNotNone(overview["latest_event_at"])

        self.assertEqual(distribution["requested_total"], 1)
        self.assertEqual(distribution["delivered_total"], 1)
        self.assertEqual(distribution["acknowledged_total"], 1)
        self.assertAlmostEqual(distribution["delivery_rate"], 100.0)
        self.assertAlmostEqual(distribution["acknowledgement_rate"], 100.0)
        self.assertEqual(distribution["channels"][0]["channel"], "push")

        self.assertEqual(tradingagents["requested_total"], 1)
        self.assertEqual(tradingagents["terminal_total"], 1)
        self.assertEqual(tradingagents["completed_total"], 1)
        self.assertEqual(tradingagents["failed_total"], 0)
        self.assertEqual(tradingagents["open_total"], 0)
        self.assertAlmostEqual(tradingagents["success_rate"], 100.0)
        self.assertAlmostEqual(tradingagents["avg_latency_seconds"], 12.5)
        self.assertEqual(
            tradingagents["by_status"],
            {
                "pending": 0,
                "submitted": 0,
                "running": 0,
                "completed": 1,
                "failed": 0,
                "timeout": 0,
            },
        )
        self.assertEqual(tradingagents["by_final_action"], {"buy": 1})

    async def test_query_strategy_health_uses_latest_rows_within_window(self) -> None:
        now = datetime.now(timezone.utc)
        await self.client.insert_rows(
            "strategy_health_events",
            [
                {
                    "occurred_at": now - timedelta(days=10),
                    "strategy_name": "stale_strategy",
                    "rank": 1,
                    "score": 1.3,
                    "degradation": 0.2,
                    "symbols_covered": 12,
                    "timeframe": "30d",
                },
                {
                    "occurred_at": now - timedelta(hours=3),
                    "strategy_name": "momentum",
                    "rank": 4,
                    "score": 0.6,
                    "degradation": 8.0,
                    "symbols_covered": 4,
                    "timeframe": "30d",
                },
                {
                    "occurred_at": now - timedelta(hours=1),
                    "strategy_name": "momentum",
                    "rank": 2,
                    "score": 0.9,
                    "degradation": 2.0,
                    "symbols_covered": 8,
                    "timeframe": "30d",
                },
                {
                    "occurred_at": now - timedelta(minutes=30),
                    "strategy_name": "breakout",
                    "rank": 1,
                    "score": 1.1,
                    "degradation": 1.2,
                    "symbols_covered": 6,
                    "timeframe": "30d",
                },
            ],
        )
        await self.client.insert_rows(
            "signal_events",
            [
                {"occurred_at": now - timedelta(hours=2), "strategy": "momentum", "symbol": "AAPL"},
                {"occurred_at": now - timedelta(hours=1), "strategy": "momentum", "symbol": "MSFT"},
                {
                    "occurred_at": now - timedelta(minutes=20),
                    "strategy": "breakout",
                    "symbol": "NVDA",
                },
            ],
        )

        result = await self.repository.query_strategy_health(24 * 7)

        self.assertEqual(len(result["strategies"]), 2)
        self.assertEqual(result["strategies"][0]["strategy_name"], "breakout")
        self.assertEqual(result["strategies"][0]["signals_generated"], 1)
        self.assertEqual(result["strategies"][1]["strategy_name"], "momentum")
        self.assertEqual(result["strategies"][1]["rank"], 2)
        self.assertEqual(result["strategies"][1]["signals_generated"], 2)
        self.assertIsNotNone(result["refreshed_at"])


if __name__ == "__main__":
    unittest.main()
