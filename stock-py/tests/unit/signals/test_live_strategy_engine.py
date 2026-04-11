import unittest

from domains.signals.live_strategy_engine import LiveStrategyEngine


def _as_dict(candidate):
    if hasattr(candidate, "model_dump"):
        return candidate.model_dump()
    return dict(candidate)


class LiveStrategyEngineTest(unittest.TestCase):
    def test_select_strategy_prefers_mean_reversion_on_large_dislocation(self) -> None:
        engine = LiveStrategyEngine()

        strategy = engine.select_strategy(
            "AAPL",
            {
                "dislocation_pct": 0.045,
                "timeframe": "30m",
                "market_regime": "range",
            },
        )

        self.assertEqual(strategy["strategy"], "mean_reversion")
        self.assertEqual(strategy["strategy_window"], "30m")

    def test_select_strategy_uses_rankings_with_regime_bias_and_setup_fit(self) -> None:
        engine = LiveStrategyEngine()

        strategy = engine.select_strategy(
            "AAPL",
            {
                "timeframe": "1d",
                "market_regime": "trend",
                "momentum_score": 0.85,
                "trend_strength": 0.78,
                "volatility_score": 0.22,
                "confidence": 82,
                "probability": 0.76,
                "analysis": {
                    "volume_confirmed": True,
                    "trend_confirmed": True,
                    "setup_quality": 84,
                },
                "strategy_rankings": [
                    {
                        "strategy_name": "mean_reversion",
                        "rank": 1,
                        "score": 30.0,
                        "degradation": 2.0,
                        "symbols_covered": 220,
                        "evidence": {"stable": True, "best_window_days": 90, "windows": {"90": {}}},
                    },
                    {
                        "strategy_name": "trend_following",
                        "rank": 2,
                        "score": 28.0,
                        "degradation": 1.0,
                        "symbols_covered": 220,
                        "evidence": {"stable": True, "best_window_days": 90, "windows": {"90": {}}},
                    },
                ],
            },
        )

        self.assertEqual(strategy["strategy"], "trend_continuation")
        self.assertEqual(strategy["source"], "ranking")
        self.assertTrue(strategy["alert_decision"]["publish_allowed"])
        self.assertGreater(strategy["combined_score"], strategy["ranking_score"])

    def test_build_signal_candidate_scores_and_normalizes_payload(self) -> None:
        engine = LiveStrategyEngine()

        candidate = engine.build_signal_candidate(
            " aapl ",
            {
                "direction": "BUY",
                "price": 182.4,
                "confidence": 84,
                "probability": 0.78,
                "risk_reward_ratio": 2.4,
                "momentum_score": 0.81,
                "trend_strength": 0.74,
                "analysis": {
                    "volume_confirmed": True,
                    "trend_confirmed": True,
                    "setup_quality": 86,
                },
                "reasons": ["Breakout above weekly range"],
            },
        )

        payload = _as_dict(candidate)
        self.assertEqual(payload["symbol"], "AAPL")
        self.assertEqual(payload["type"], "buy")
        self.assertGreaterEqual(payload["score"], 80)
        self.assertEqual(payload["analysis"]["strategy"], "trend_continuation")
        self.assertEqual(payload["analysis"]["market_regime"], "trend")

    def test_build_signal_candidate_keeps_suppressed_alert_decision_metadata(self) -> None:
        engine = LiveStrategyEngine()

        candidate = engine.build_signal_candidate(
            "AAPL",
            {
                "direction": "buy",
                "price": 100.0,
                "timeframe": "1d",
                "market_regime": "trend",
                "confidence": 40,
                "probability": 0.4,
                "analysis": {"setup_quality": 45},
                "strategy_rankings": [
                    {
                        "strategy_name": "mean_reversion",
                        "rank": 1,
                        "score": 4.0,
                        "degradation": 14.0,
                        "symbols_covered": 12,
                        "evidence": {"stable": False, "best_window_days": 30, "windows": {"30": {}}},
                    }
                ],
            },
        )

        payload = _as_dict(candidate)
        self.assertFalse(payload["analysis"]["alert_decision"]["publish_allowed"])
        self.assertIn(
            "strategy-degradation-detected",
            payload["analysis"]["alert_decision"]["suppressed_reasons"],
        )

    def test_select_strategy_suppresses_weak_breakout_candidates(self) -> None:
        engine = LiveStrategyEngine()

        strategy = engine.select_strategy(
            "AAPL",
            {
                "timeframe": "1d",
                "market_regime": "volatile",
                "momentum_score": 0.52,
                "trend_strength": 0.34,
                "volatility_score": 1.0,
                "confidence": 50,
                "probability": 0.5,
                "analysis": {
                    "trend_confirmed": True,
                    "volume_confirmed": False,
                    "setup_quality": 52,
                },
                "strategy_rankings": [
                    {
                        "strategy_name": "breakout",
                        "rank": 1,
                        "score": 10.0,
                        "degradation": 1.0,
                        "symbols_covered": 220,
                        "evidence": {"stable": True, "best_window_days": 90, "windows": {"90": {}}},
                    }
                ],
            },
        )

        self.assertEqual(strategy["strategy"], "volatility_breakout")
        self.assertFalse(strategy["alert_decision"]["publish_allowed"])
        self.assertIn(
            "breakout-confidence-weak",
            strategy["alert_decision"]["suppressed_reasons"],
        )

    def test_select_strategy_suppresses_benchmark_only_source_strategies(self) -> None:
        engine = LiveStrategyEngine()

        strategy = engine.select_strategy(
            "AAPL",
            {
                "timeframe": "1d",
                "market_regime": "trend",
                "momentum_score": 0.85,
                "trend_strength": 0.9,
                "volatility_score": 0.35,
                "confidence": 80,
                "probability": 0.72,
                "analysis": {
                    "trend_confirmed": True,
                    "volume_confirmed": True,
                    "setup_quality": 88,
                },
                "strategy_rankings": [
                    {
                        "strategy_name": "buy_and_hold",
                        "rank": 1,
                        "score": 14.0,
                        "degradation": 0.5,
                        "symbols_covered": 220,
                        "evidence": {"stable": True, "best_window_days": 90, "windows": {"90": {}}},
                    }
                ],
            },
        )

        self.assertEqual(strategy["source_strategy"], "buy_and_hold")
        self.assertFalse(strategy["alert_decision"]["publish_allowed"])
        self.assertIn(
            "benchmark-only-strategy",
            strategy["alert_decision"]["suppressed_reasons"],
        )

    def test_build_signal_candidate_returns_none_without_price_or_direction(self) -> None:
        engine = LiveStrategyEngine()

        self.assertIsNone(engine.build_signal_candidate("AAPL", {"price": 100}))
        self.assertIsNone(engine.build_signal_candidate("AAPL", {"direction": "buy"}))


if __name__ == "__main__":
    unittest.main()
