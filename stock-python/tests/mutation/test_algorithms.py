"""
Mutation tests for signal algorithms.

These tests verify that the algorithm implementations are robust against
code mutations (which could represent bugs or security issues).
"""
import numpy as np
import pytest

from domains.signals.advanced_algorithms import (
    AdvancedSignalGenerator,
    MarketRegime,
    MarketRegimeDetector,
    MultiTimeframeAnalyzer,
    PatternRecognizer,
    TrendDirection,
    TrendStrengthCalculator,
    VolumeProfileAnalyzer,
)


class TestAdvancedAlgorithmsMutationResistance:
    """Test that algorithms are resilient to edge cases."""

    def test_trend_direction_empty_data(self):
        """Ensure algorithm handles empty data gracefully."""
        analyzer = MultiTimeframeAnalyzer()
        result = analyzer.analyze({})
        assert result["confirm"] is False
        assert result["trend_agreement"] == 0

    def test_trend_direction_single_timeframe(self):
        """Ensure single timeframe returns neutral."""
        analyzer = MultiTimeframeAnalyzer()
        data = {"1h": {"close": [100] * 25}}
        result = analyzer.analyze(data)
        assert result["confirm"] is False

    def test_volume_profile_insufficient_data(self):
        """Ensure volume analysis handles insufficient data."""
        result = VolumeProfileAnalyzer.analyze(
            close=[100],
            high=[105],
            low=[95],
            volume=[1000],
            lookback=20,
        )
        assert result["confirm"] is False

    def test_pattern_recognition_minimal_data(self):
        """Ensure pattern recognition handles minimal data."""
        result = PatternRecognizer.recognize(
            close=[100, 101, 102],
            high=[103],
            low=[99],
            volume=[1000],
        )
        assert "patterns" in result

    def test_trend_strength_insufficient_data(self):
        """Ensure trend strength handles insufficient data."""
        result = TrendStrengthCalculator.calculate(
            close=[100],
            high=[105],
            low=[95],
            volume=[1000],
            lookback=20,
        )
        assert result["strength"] == 0

    def test_market_regime_insufficient_data(self):
        """Ensure regime detection handles insufficient data."""
        result = MarketRegimeDetector.detect(
            close=[100],
            high=[105],
            low=[95],
            volume=[1000],
        )
        assert result["regime"] == MarketRegime.CONSOLIDATING

    def test_signal_generator_no_data(self):
        """Ensure signal generator handles no data."""
        generator = AdvancedSignalGenerator()
        result = generator.generate({})
        assert result is None

    def test_signal_generator_minimal_data(self):
        """Ensure signal generator handles minimal data."""
        generator = AdvancedSignalGenerator()
        data = {
            "close": list(range(90, 120)),
            "high": [i + 5 for i in range(90, 120)],
            "low": [i - 5 for i in range(90, 120)],
            "volume": [1000] * 30,
        }
        result = generator.generate(data)
        # Should return a valid result or None, but not crash
        assert result is None or hasattr(result, "direction")


class TestAlgorithmProperties:
    """Property-based tests for algorithm invariants."""

    def test_multi_tf_analyzer_returns_valid_direction(self):
        """Multi-TF analyzer should always return valid direction."""
        analyzer = MultiTimeframeAnalyzer()
        data = {
            "1h": {"close": list(np.linspace(100, 110, 30))},
            "4h": {"close": list(np.linspace(100, 110, 30))},
            "1d": {"close": list(np.linspace(100, 110, 30))},
        }
        result = analyzer.analyze(data)
        assert "confirm" in result
        assert "trend_agreement" in result

    def test_volume_profile_returns_valid_dict(self):
        """Volume profile should always return required keys."""
        close = list(np.linspace(90, 110, 30))
        result = VolumeProfileAnalyzer.analyze(
            close=close,
            high=[c + 5 for c in close],
            low=[c - 5 for c in close],
            volume=[1000] * 30,
        )
        required_keys = {"confirm", "volume_trend", "vwap", "price_vs_vwap"}
        assert required_keys.issubset(result.keys())

    def test_pattern_recognizer_returns_dict(self):
        """Pattern recognizer should always return a dict."""
        close = list(np.linspace(90, 110, 30))
        result = PatternRecognizer.recognize(
            close=close,
            high=[c + 5 for c in close],
            low=[c - 5 for c in close],
            volume=[1000] * 30,
        )
        assert isinstance(result, dict)
        assert "patterns" in result

    def test_trend_strength_returns_valid_rating(self):
        """Trend strength should always return valid rating."""
        close = list(np.linspace(90, 110, 30))
        result = TrendStrengthCalculator.calculate(
            close=close,
            high=[c + 5 for c in close],
            low=[c - 5 for c in close],
            volume=[1000] * 30,
        )
        valid_ratings = {"weak", "moderate", "strong"}
        assert result["rating"] in valid_ratings

    def test_market_regime_returns_valid_regime(self):
        """Market regime should always return valid regime."""
        close = list(np.linspace(90, 110, 30))
        result = MarketRegimeDetector.detect(
            close=close,
            high=[c + 5 for c in close],
            low=[c - 5 for c in close],
            volume=[1000] * 30,
        )
        valid_regimes = {r.value for r in MarketRegime}
        assert result["regime"].value in valid_regimes


class TestAlgorithmDeterminism:
    """Test that algorithms are deterministic."""

    def test_same_input_same_output(self):
        """Same input should produce same output."""
        close = list(np.linspace(100, 110, 50))
        data = {"close": close, "high": [c + 5 for c in close], "low": [c - 5 for c in close], "volume": [1000] * 50}

        result1 = TrendStrengthCalculator.calculate(**data)
        result2 = TrendStrengthCalculator.calculate(**data)
        assert result1 == result2

    def test_signal_generator_deterministic(self):
        """Signal generator should be deterministic."""
        generator = AdvancedSignalGenerator()
        data = {
            "close": list(np.linspace(100, 110, 30)),
            "high": [c + 5 for c in np.linspace(100, 110, 30)],
            "low": [c - 5 for c in np.linspace(100, 110, 30)],
            "volume": [1000] * 30,
        }

        result1 = generator.generate(data)
        result2 = generator.generate(data)

        if result1 is not None and result2 is not None:
            assert result1.direction == result2.direction
            assert result1.confidence == result2.confidence
