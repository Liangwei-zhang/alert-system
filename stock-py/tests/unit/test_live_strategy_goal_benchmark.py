import unittest

from run_live_strategy_goal_benchmark import (
    aggregate_trade_metrics,
    build_goal_evaluation,
    calculate_relative_uplift_percent,
    resolve_baseline_strategy,
    resolve_concrete_strategy,
)


class LiveStrategyGoalBenchmarkTest(unittest.TestCase):
    def test_resolve_concrete_strategy_maps_live_categories(self):
        self.assertEqual(resolve_concrete_strategy("trend_continuation"), "trend_following")
        self.assertEqual(resolve_concrete_strategy("volatility_breakout"), "breakout")
        self.assertEqual(resolve_concrete_strategy("range_rotation"), "rsi_reversion")

    def test_resolve_baseline_strategy_supports_rsi_proxy_and_legacy_heuristic(self):
        self.assertEqual(resolve_baseline_strategy("rsi_proxy", {}), "rsi_reversion")
        self.assertEqual(
            resolve_baseline_strategy(
                "",
                {"dislocation_pct": 0.0, "momentum_score": 0.8, "volatility_score": 0.1},
            ),
            "trend_following",
        )
        self.assertEqual(
            resolve_baseline_strategy(
                "legacy_heuristic",
                {"dislocation_pct": 0.01, "momentum_score": 0.72, "volatility_score": 0.2},
            ),
            "trend_following",
        )
        self.assertEqual(
            resolve_baseline_strategy(
                "legacy_heuristic",
                {"dislocation_pct": 0.0, "momentum_score": 0.1, "volatility_score": 0.1},
            ),
            "rsi_reversion",
        )

    def test_aggregate_trade_metrics_calculates_trade_weighted_win_rate(self):
        metrics = aggregate_trade_metrics(
            [
                {
                    "trades": [
                        {"return_percent": 4.2},
                        {"return_percent": -1.1},
                    ],
                    "metrics": {"total_return_percent": 8.5},
                },
                {
                    "trades": [
                        {"return_percent": 2.0},
                    ],
                    "metrics": {"total_return_percent": 5.0},
                },
            ]
        )

        self.assertEqual(metrics["symbol_count"], 2)
        self.assertEqual(metrics["trade_count"], 3)
        self.assertEqual(metrics["winning_trades"], 2)
        self.assertEqual(metrics["win_rate"], 66.6667)
        self.assertEqual(metrics["mean_total_return_percent"], 6.75)

    def test_build_goal_evaluation_marks_target_as_met(self):
        goal = build_goal_evaluation(
            new_win_rate=65.5814,
            baseline_win_rate=54.6875,
            target_new_win_rate=65.58,
            target_absolute_uplift=10.89,
            target_relative_uplift=19.92,
        )

        self.assertTrue(goal["met"])
        self.assertTrue(goal["checks"]["new_win_rate"]["passed"])
        self.assertTrue(goal["checks"]["absolute_uplift_pp"]["passed"])
        self.assertTrue(goal["checks"]["relative_uplift_percent"]["passed"])

    def test_zero_baseline_win_rate_is_treated_as_unbounded_relative_uplift(self):
        self.assertIsNone(
            calculate_relative_uplift_percent(new_win_rate=100.0, baseline_win_rate=0.0)
        )

        goal = build_goal_evaluation(
            new_win_rate=100.0,
            baseline_win_rate=0.0,
            target_new_win_rate=65.58,
            target_absolute_uplift=10.89,
            target_relative_uplift=19.92,
        )

        self.assertTrue(goal["met"])
        self.assertIsNone(goal["checks"]["relative_uplift_percent"]["actual"])
        self.assertEqual(
            goal["checks"]["relative_uplift_percent"]["basis"],
            "baseline_win_rate_zero",
        )
        self.assertTrue(goal["checks"]["relative_uplift_percent"]["passed"])


if __name__ == "__main__":
    unittest.main()