from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.admin_api.dependencies import get_clickhouse_analytics_client
from apps.admin_api.routers import analytics
from apps.workers.analytics_sink.worker import AnalyticsSinkWorker
from infra.analytics.clickhouse_client import ClickHouseClient


class AdminAnalyticsPipelineIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.analytics_client = ClickHouseClient(root_path=self.tempdir.name)
        self.worker = AnalyticsSinkWorker(client=self.analytics_client)

        app = FastAPI()
        app.include_router(analytics.router)

        async def override_clickhouse_client() -> ClickHouseClient:
            return self.analytics_client

        app.dependency_overrides[get_clickhouse_analytics_client] = override_clickhouse_client
        self.http_client = TestClient(app)
        self.addCleanup(self.http_client.close)

    async def test_admin_analytics_routes_reflect_ingested_events(self) -> None:
        now = datetime.now(timezone.utc)
        stale = (now - timedelta(days=3)).isoformat()
        current = now.isoformat()
        one_hour_ago = (now - timedelta(hours=1)).isoformat()

        await self.worker.process_events(
            [
                (
                    "signal.generated",
                    {
                        "occurred_at": current,
                        "signal_id": 1,
                        "symbol": "AAPL",
                        "signal_type": "buy",
                        "price": 100.0,
                        "user_ids": [7, 9],
                        "analysis": {
                            "strategy": "momentum",
                            "market_regime": "trend",
                            "market_regime_detail": "trend_strong_up",
                            "exit_levels": {
                                "source": "server_default",
                                "atr_multiplier_source": "calibration_snapshot",
                                "atr_multiplier": 2.25,
                                "stop_loss": 94.0,
                                "take_profit_1": 109.0,
                            },
                        },
                    },
                ),
                (
                    "signal.generated",
                    {
                        "occurred_at": one_hour_ago,
                        "signal_id": 2,
                        "symbol": "MSFT",
                        "signal_type": "buy",
                        "price": 200.0,
                        "user_ids": [5],
                        "analysis": {
                            "strategy": "breakout",
                            "market_regime": "trend",
                            "market_regime_detail": "volatile_breakout",
                            "exit_levels": {
                                "source": "client",
                                "atr_multiplier_source": "client",
                                "atr_multiplier": 1.85,
                                "stop_loss": 190.0,
                                "take_profit_1": 220.0,
                            },
                        },
                    },
                ),
                (
                    "signal.generated",
                    {
                        "occurred_at": stale,
                        "signal_id": 3,
                        "symbol": "TSLA",
                        "signal_type": "sell",
                        "analysis": {"strategy": "stale", "market_regime": "range"},
                    },
                ),
                (
                    "scanner.decision.recorded",
                    {
                        "occurred_at": current,
                        "decision_id": 11,
                        "run_id": 5,
                        "symbol": "AAPL",
                        "decision": "emitted",
                        "signal_type": "buy",
                        "strategy": "momentum",
                    },
                ),
                (
                    "notification.requested",
                    {
                        "occurred_at": current,
                        "notification_id": 50,
                        "user_id": 1,
                        "channel": "push",
                    },
                ),
                (
                    "notification.requested",
                    {
                        "occurred_at": current,
                        "notification_id": 51,
                        "user_id": 1,
                        "channel": "email",
                    },
                ),
                (
                    "notification.requested",
                    {
                        "occurred_at": stale,
                        "notification_id": 52,
                        "user_id": 2,
                        "channel": "sms",
                    },
                ),
                (
                    "notification.delivered",
                    {
                        "occurred_at": current,
                        "notification_id": 50,
                        "user_id": 1,
                        "channel": "push",
                    },
                ),
                (
                    "notification.acknowledged",
                    {
                        "occurred_at": current,
                        "notification_id": 50,
                        "receipt_id": 3,
                        "user_id": 1,
                        "channel": "push",
                    },
                ),
                (
                    "trade.action.recorded",
                    {
                        "occurred_at": current,
                        "trade_id": "T-1",
                        "action": "buy",
                        "symbol": "AAPL",
                    },
                ),
                (
                    "account.subscription.started",
                    {"occurred_at": current, "user_id": 8, "plan_code": "pro"},
                ),
                (
                    "tradingagents.requested",
                    {
                        "occurred_at": current,
                        "request_id": "req-1",
                        "ticker": "AAPL",
                        "trigger_type": "signal",
                    },
                ),
                (
                    "tradingagents.requested",
                    {
                        "occurred_at": current,
                        "request_id": "req-2",
                        "ticker": "MSFT",
                        "trigger_type": "signal",
                    },
                ),
                (
                    "tradingagents.terminal",
                    {
                        "occurred_at": current,
                        "request_id": "req-1",
                        "ticker": "AAPL",
                        "status": "completed",
                        "final_action": "buy",
                        "submitted_at": (now - timedelta(seconds=42)).isoformat(),
                        "completed_at": current,
                    },
                ),
                (
                    "strategy.rankings.refreshed",
                    {
                        "occurred_at": (now - timedelta(hours=2)).isoformat(),
                        "timeframe": "30d",
                        "rankings": [
                            {
                                "strategy_name": "momentum",
                                "rank": 4,
                                "score": 0.4,
                                "symbols_covered": 3,
                            }
                        ],
                    },
                ),
                (
                    "strategy.rankings.refreshed",
                    {
                        "occurred_at": current,
                        "timeframe": "30d",
                        "rankings": [
                            {
                                "strategy_name": "breakout",
                                "rank": 1,
                                "score": 1.2,
                                "symbols_covered": 6,
                                "top_symbols": [{"symbol": "MSFT", "score": 1.2}],
                                "evidence": {"stable": True},
                            },
                            {
                                "strategy_name": "momentum",
                                "rank": 2,
                                "score": 0.9,
                                "symbols_covered": 8,
                                "top_symbols": [{"symbol": "AAPL", "score": 0.9}],
                                "evidence": {"stable": False},
                            },
                        ],
                    },
                ),
            ]
        )

        overview = self.http_client.get("/v1/admin/analytics/overview", params={"window_hours": 24})
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(
            overview.json(),
            {
                "window_hours": 24,
                "generated_signals": 2,
                "scanner_decisions": 1,
                "notification_requests": 2,
                "delivered_notifications": 1,
                "acknowledged_notifications": 1,
                "trade_actions": 1,
                "subscriptions_started": 1,
                "tradingagents_terminals": 1,
                "latest_event_at": overview.json()["latest_event_at"],
            },
        )
        self.assertIsNotNone(overview.json()["latest_event_at"])

        distribution = self.http_client.get(
            "/v1/admin/analytics/distribution", params={"window_hours": 24}
        )
        self.assertEqual(distribution.status_code, 200)
        self.assertEqual(
            distribution.json(),
            {
                "window_hours": 24,
                "requested_total": 2,
                "delivered_total": 1,
                "acknowledged_total": 1,
                "pending_acknowledgements": 1,
                "delivery_rate": 50.0,
                "acknowledgement_rate": 100.0,
                "channels": [
                    {"channel": "email", "requested": 1, "delivered": 0},
                    {"channel": "push", "requested": 1, "delivered": 1},
                ],
            },
        )

        strategy_health = self.http_client.get(
            "/v1/admin/analytics/strategy-health", params={"window_hours": 24 * 7}
        )
        self.assertEqual(strategy_health.status_code, 200)
        strategy_payload = strategy_health.json()
        self.assertEqual(strategy_payload["window_hours"], 168)
        self.assertEqual(len(strategy_payload["strategies"]), 2)
        self.assertEqual(strategy_payload["strategies"][0]["strategy_name"], "breakout")
        self.assertEqual(strategy_payload["strategies"][0]["signals_generated"], 1)
        self.assertEqual(strategy_payload["strategies"][1]["strategy_name"], "momentum")
        self.assertEqual(strategy_payload["strategies"][1]["rank"], 2)
        self.assertEqual(strategy_payload["strategies"][1]["signals_generated"], 1)
        self.assertFalse(strategy_payload["strategies"][1]["stable"])
        self.assertIsNotNone(strategy_payload["refreshed_at"])

        signal_results = self.http_client.get(
            "/v1/admin/analytics/signal-results", params={"window_hours": 24}
        )
        self.assertEqual(signal_results.status_code, 200)
        self.assertEqual(
            signal_results.json(),
            {
                "window_hours": 24,
                "generated_after": signal_results.json()["generated_after"],
                "total_signals": 2,
                "total_trade_actions": 1,
                "confirmed_trades": 0,
                "adjusted_trades": 0,
                "ignored_trades": 0,
                "expired_trades": 0,
                "pending_trades": 0,
                "trade_action_rate": 50.0,
                "executed_trade_rate": 0.0,
                "unique_signal_symbols": 2,
                "unique_trade_symbols": 1,
                "overlapping_symbols": 1,
                "signal_strategies": [
                    {"key": "breakout", "count": 1},
                    {"key": "momentum", "count": 1},
                ],
                "market_regimes": [
                    {"key": "trend", "count": 2},
                ],
                "trade_statuses": [
                    {"key": "unknown", "count": 1},
                ],
                "symbol_alignment": [
                    {
                        "symbol": "AAPL",
                        "signals_generated": 1,
                        "trade_actions": 1,
                        "executed_trades": 0,
                        "execution_rate": 0.0,
                    }
                ],
                "comparable_field_sets": [
                    {
                        "category": "live_signals",
                        "fields": [
                            "symbol",
                            "signal_type",
                            "strategy",
                            "strategy_window",
                            "market_regime",
                            "score",
                        ],
                        "note": "来自 signal.generated / signal_events。",
                    },
                    {
                        "category": "trade_actions",
                        "fields": [
                            "symbol",
                            "action",
                            "status",
                            "actual_price",
                            "actual_amount",
                        ],
                        "note": "来自 trade.action.recorded / trade_events；当前按窗口与 symbol 做近似对齐。",
                    },
                    {
                        "category": "backtests",
                        "fields": [
                            "symbol",
                            "strategy_name",
                            "timeframe",
                            "window_days",
                            "score",
                            "degradation",
                        ],
                        "note": "与 live signal 的可比字段已明确，但当前响应暂不直接联表 backtest_runs。",
                    },
                ],
            },
        )

        exit_quality = self.http_client.get(
            "/v1/admin/analytics/exit-quality", params={"window_hours": 24}
        )
        self.assertEqual(exit_quality.status_code, 200)
        self.assertEqual(
            exit_quality.json(),
            {
                "window_hours": 24,
                "generated_after": exit_quality.json()["generated_after"],
                "total_signals": 2,
                "exits_available": 2,
                "calibrated_exit_count": 1,
                "client_exit_count": 1,
                "avg_risk_reward_ratio": 1.75,
                "avg_atr_multiplier": 2.05,
                "avg_stop_distance_pct": 5.5,
                "avg_tp1_distance_pct": 9.5,
                "exit_sources": [
                    {"key": "client", "count": 1},
                    {"key": "server_default", "count": 1},
                ],
                "atr_multiplier_sources": [
                    {"key": "calibration_snapshot", "count": 1},
                    {"key": "client", "count": 1},
                ],
                "market_regimes": [
                    {"key": "trend_strong_up", "count": 1},
                    {"key": "volatile_breakout", "count": 1},
                ],
                "top_symbols": [
                    {"key": "AAPL", "count": 1},
                    {"key": "MSFT", "count": 1},
                ],
            },
        )

        tradingagents = self.http_client.get(
            "/v1/admin/analytics/tradingagents", params={"window_hours": 24}
        )
        self.assertEqual(tradingagents.status_code, 200)
        self.assertEqual(
            tradingagents.json(),
            {
                "window_hours": 24,
                "requested_total": 2,
                "terminal_total": 1,
                "completed_total": 1,
                "failed_total": 0,
                "open_total": 1,
                "success_rate": 100.0,
                "avg_latency_seconds": 42.0,
                "by_status": {
                    "pending": 1,
                    "submitted": 0,
                    "running": 0,
                    "completed": 1,
                    "failed": 0,
                    "timeout": 0,
                },
                "by_final_action": {"buy": 1},
            },
        )

    async def test_admin_analytics_routes_honor_window_hours(self) -> None:
        now = datetime.now(timezone.utc)
        await self.worker.process_events(
            [
                (
                    "signal.generated",
                    {
                        "occurred_at": (now - timedelta(hours=2)).isoformat(),
                        "signal_id": 1,
                        "symbol": "AAPL",
                        "analysis": {"strategy": "momentum"},
                    },
                ),
                (
                    "signal.generated",
                    {
                        "occurred_at": now.isoformat(),
                        "signal_id": 2,
                        "symbol": "MSFT",
                        "analysis": {"strategy": "breakout"},
                    },
                ),
            ]
        )

        one_hour = self.http_client.get("/v1/admin/analytics/overview", params={"window_hours": 1})
        three_hours = self.http_client.get(
            "/v1/admin/analytics/overview", params={"window_hours": 3}
        )

        self.assertEqual(one_hour.status_code, 200)
        self.assertEqual(one_hour.json()["generated_signals"], 1)
        self.assertEqual(three_hours.status_code, 200)
        self.assertEqual(three_hours.json()["generated_signals"], 2)


if __name__ == "__main__":
    unittest.main()
