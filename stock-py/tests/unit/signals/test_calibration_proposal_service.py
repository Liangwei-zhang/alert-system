from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from domains.signals.calibration_proposal_service import CalibrationProposalService


class FakeAnalyticsRepository:
    async def query_strategy_health(self, window_hours: int = 168):
        now = datetime(2026, 4, 11, 8, 0, tzinfo=timezone.utc)
        return {
            "window_hours": window_hours,
            "strategies": [
                {
                    "strategy_name": "momentum",
                    "rank": 1,
                    "score": 1.18,
                    "degradation": 1.5,
                    "signals_generated": 18,
                    "stable": True,
                },
                {
                    "strategy_name": "breakout",
                    "rank": 2,
                    "score": 1.04,
                    "degradation": 2.5,
                    "signals_generated": 11,
                    "stable": True,
                },
                {
                    "strategy_name": "mean_reversion",
                    "rank": 4,
                    "score": 0.86,
                    "degradation": 11.0,
                    "signals_generated": 6,
                    "stable": False,
                },
            ],
            "refreshed_at": now,
        }

    async def query_signal_results(self, window_hours: int = 24):
        now = datetime(2026, 4, 11, 8, 0, tzinfo=timezone.utc)
        return {
            "window_hours": window_hours,
            "generated_after": now - timedelta(hours=window_hours),
            "total_signals": 64,
            "total_trade_actions": 18,
            "trade_action_rate": 28.125,
            "executed_trade_rate": 17.1875,
            "overlapping_symbols": 9,
            "signal_strategies": [
                {"key": "momentum", "count": 30},
                {"key": "breakout", "count": 18},
                {"key": "mean_reversion", "count": 10},
                {"key": "range_rotation", "count": 6},
            ],
            "market_regimes": [
                {"key": "trend_up", "count": 39},
                {"key": "range", "count": 17},
            ],
        }


class FakeCalibrationRepository:
    async def get_active_snapshot(self):
        return {
            "version": "signals-v2-review-20260410",
            "source": "manual_review",
            "strategy_weights": {
                "trend_continuation": 1.04,
                "mean_reversion": 0.98,
                "volatility_breakout": 1.0,
                "range_rotation": 1.0,
            },
            "score_multipliers": {
                "confidence": 1.0,
                "probability": 1.0,
                "risk_reward": 1.0,
                "quality": 1.0,
                "volume": 1.0,
                "trend": 1.0,
                "reversal": 1.0,
                "stale_penalty": 1.0,
                "liquidity_penalty": 1.0,
            },
        }


class CalibrationProposalServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_build_proposal_generates_bounded_recommendations(self) -> None:
        service = CalibrationProposalService(
            analytics_repository=FakeAnalyticsRepository(),
            calibration_repository=FakeCalibrationRepository(),
        )

        proposal = await service.build_proposal(signal_window_hours=24, ranking_window_hours=168)

        self.assertEqual(proposal["current_version"], "signals-v2-review-20260410")
        self.assertTrue(proposal["proposed_version"].startswith("signals-v2-proposal-"))
        self.assertEqual(proposal["summary"]["total_signals"], 64)
        self.assertEqual(proposal["snapshot_payload"]["source"], "proposal")

        strategy_weights = {item["key"]: item for item in proposal["strategy_weights"]}
        self.assertGreater(
            strategy_weights["trend_continuation"]["proposed_value"],
            strategy_weights["trend_continuation"]["current_value"],
        )
        self.assertLess(
            strategy_weights["mean_reversion"]["proposed_value"],
            strategy_weights["mean_reversion"]["current_value"],
        )
        self.assertGreaterEqual(strategy_weights["trend_continuation"]["proposed_value"], 0.75)
        self.assertLessEqual(strategy_weights["trend_continuation"]["proposed_value"], 1.25)

        score_multipliers = {item["key"]: item for item in proposal["score_multipliers"]}
        self.assertLess(score_multipliers["confidence"]["proposed_value"], 1.0)
        self.assertGreater(score_multipliers["trend"]["proposed_value"], 1.0)
        self.assertGreater(score_multipliers["stale_penalty"]["proposed_value"], 1.0)


if __name__ == "__main__":
    unittest.main()