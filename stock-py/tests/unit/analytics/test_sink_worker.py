import tempfile
import unittest
from datetime import datetime, timezone

from apps.workers.analytics_sink.worker import AnalyticsSinkWorker
from infra.analytics.clickhouse_client import ClickHouseClient


class AnalyticsSinkWorkerTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.client = ClickHouseClient(root_path=self.tempdir.name)
        self.worker = AnalyticsSinkWorker(client=self.client)

    async def test_process_events_routes_supported_topics(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        result = await self.worker.process_events(
            [
                (
                    "signal.generated",
                    {
                        "occurred_at": now,
                        "signal_id": 1,
                        "symbol": "AAPL",
                        "signal_type": "buy",
                        "user_ids": [7, 9],
                        "analysis": {"strategy": "momentum", "market_regime": "trend"},
                    },
                ),
                (
                    "scanner.decision.recorded",
                    {
                        "occurred_at": now,
                        "decision_id": 11,
                        "run_id": 5,
                        "symbol": "AAPL",
                        "decision": "emitted",
                        "signal_type": "buy",
                    },
                ),
                (
                    "notification.requested",
                    {
                        "occurred_at": now,
                        "notification_id": 50,
                        "user_id": 1,
                        "channel": "push",
                    },
                ),
                (
                    "notification.delivered",
                    {
                        "occurred_at": now,
                        "notification_id": 50,
                        "user_id": 1,
                        "channel": "push",
                    },
                ),
                (
                    "notification.acknowledged",
                    {
                        "occurred_at": now,
                        "notification_id": 50,
                        "receipt_id": 3,
                        "user_id": 1,
                    },
                ),
                (
                    "trade.action.recorded",
                    {"occurred_at": now, "trade_id": "T-1", "action": "buy", "symbol": "AAPL"},
                ),
                (
                    "account.subscription.started",
                    {"occurred_at": now, "user_id": 8, "plan_code": "pro"},
                ),
                (
                    "tradingagents.requested",
                    {
                        "occurred_at": now,
                        "request_id": "req-1",
                        "ticker": "AAPL",
                        "trigger_type": "signal",
                    },
                ),
                (
                    "tradingagents.terminal",
                    {
                        "occurred_at": now,
                        "request_id": "req-1",
                        "ticker": "AAPL",
                        "status": "completed",
                        "final_action": "buy",
                        "submitted_at": now,
                        "completed_at": now,
                    },
                ),
                (
                    "strategy.rankings.refreshed",
                    {
                        "occurred_at": now,
                        "timeframe": "30d",
                        "rankings": [
                            {
                                "strategy_name": "momentum",
                                "rank": 1,
                                "score": 1.2,
                                "symbols_covered": 7,
                            },
                            {
                                "strategy_name": "breakout",
                                "rank": 2,
                                "score": 0.9,
                                "symbols_covered": 5,
                            },
                        ],
                    },
                ),
                ("unknown.topic", {}),
            ]
        )

        self.assertEqual(result["handled"], 10)
        self.assertEqual(result["ignored"], 1)
        self.assertEqual(result["failed"], 0)

        self.assertEqual(len(await self.client.query_rows("signal_events")), 1)
        self.assertEqual(len(await self.client.query_rows("scanner_decision_events")), 1)
        self.assertEqual(len(await self.client.query_rows("notification_events")), 2)
        self.assertEqual(len(await self.client.query_rows("receipt_events")), 1)
        self.assertEqual(len(await self.client.query_rows("trade_events")), 1)
        self.assertEqual(len(await self.client.query_rows("subscription_events")), 1)
        self.assertEqual(len(await self.client.query_rows("tradingagents_events")), 2)
        self.assertEqual(len(await self.client.query_rows("strategy_health_events")), 2)


if __name__ == "__main__":
    unittest.main()
