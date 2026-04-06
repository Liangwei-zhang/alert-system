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

    def test_build_signal_candidate_returns_none_without_price_or_direction(self) -> None:
        engine = LiveStrategyEngine()

        self.assertIsNone(engine.build_signal_candidate("AAPL", {"price": 100}))
        self.assertIsNone(engine.build_signal_candidate("AAPL", {"direction": "buy"}))


if __name__ == "__main__":
    unittest.main()
