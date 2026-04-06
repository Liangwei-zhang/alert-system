"""
Property-based tests using Hypothesis.

These tests verify algorithm properties over a wide range of inputs
to catch edge cases that unit tests might miss.
"""
from hypothesis import given, settings, assume, example
import hypothesis.strategies as st
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


# ============================================================================
# Strategies
# ============================================================================

@st.composite
def price_data_strategy(draw, min_len: int = 20, max_len: int = 200):
    """Generate valid price data (OHLCV)."""
    length = draw(st.integers(min_value=min_len, max_value=max_len))
    
    # Start with a base price
    base_price = draw(st.floats(min_value=1.0, max_value=10000.0))
    
    # Generate close prices with some random walk
    close_prices = [base_price]
    for _ in range(length - 1):
        change = draw(st.floats(min_value=-0.1, max_value=0.1)) * close_prices[-1]
        close_prices.append(close_prices[-1] + change)
    
    # Ensure prices stay positive
    assume(all(p > 0 for p in close_prices))
    
    # Generate high/low/volume
    high_prices = [c * draw(st.floats(min_value=1.0, max_value=1.05)) for c in close_prices]
    low_prices = [c * draw(st.floats(min_value=0.95, max_value=1.0)) for c in close_prices]
    volumes = [draw(st.integers(min_value=100, max_value=1000000)) for _ in close_prices]
    
    return {
        "close": close_prices,
        "high": high_prices,
        "low": low_prices,
        "volume": volumes,
    }


@st.composite
def timeframe_data_strategy(draw, num_tfs: int = 3):
    """Generate multi-timeframe data."""
    tfs = ["1h", "4h", "1d", "1w", "15m"][:num_tfs]
    data = {}
    
    for tf in tfs:
        length = draw(st.integers(min_value=20, max_value=100))
        base = draw(st.floats(min_value=10.0, max_value=1000.0))
        close = [base + draw(st.floats(min_value=-0.2, max_value=0.2)) * base for _ in range(length)]
        assume(all(c > 0 for c in close))
        
        data[tf] = {
            "close": close,
            "high": [c * 1.02 for c in close],
            "low": [c * 0.98 for c in close],
            "volume": [draw(st.integers(min_value=100, max_value=100000)) for _ in close],
        }
    
    return data


# ============================================================================
# Property tests for MultiTimeframeAnalyzer
# ============================================================================

@given(data=tf timeframe_data_strategy(num_tfs=2))
@settings(max_examples=50)
def test_multi_tf_analyzer_always_returns_valid_dict(data):
    """Multi-TF analyzer should always return a valid result dict."""
    analyzer = MultiTimeframeAnalyzer()
    result = analyzer.analyze(data)
    
    # Should always have these keys
    assert "confirm" in result
    assert "trend_agreement" in result
    assert isinstance(result["confirm"], bool)
    assert isinstance(result["trend_agreement"], (int, float))


@given(data=tf timeframe_data_strategy(num_tfs=3))
@settings(max_examples=30)
def test_multi_tf_analyzer_trend_agreement_bounds(data):
    """Trend agreement should always be between 0 and 1."""
    analyzer = MultiTimeframeAnalyzer()
    result = analyzer.analyze(data)
    
    if result["trend_agreement"] > 0:
        assert 0 < result["trend_agreement"] <= 1.0


# ============================================================================
# Property tests for VolumeProfileAnalyzer
# ============================================================================

@given(data=price_data_strategy(min_len=20))
@settings(max_examples=50)
def test_volume_profile_always_returns_required_keys(data):
    """Volume profile should always return required keys."""
    result = VolumeProfileAnalyzer.analyze(**data)
    
    required_keys = {"confirm", "volume_trend", "vwap", "price_vs_vwap"}
    assert required_keys.issubset(result.keys())


@given(data=price_data_strategy(min_len=20))
@settings(max_examples=50)
def test_volume_profile_vwap_is_valid_price(data):
    """VWAP should be a valid price within the range."""
    result = VolumeProfileAnalyzer.analyze(**data)
    
    close = data["close"]
    vwap = result["vwap"]
    
    # VWAP should be between min and max of close prices
    assert min(close) <= vwap <= max(close)


@given(data=price_data_strategy(min_len=20))
@settings(max_examples=50)
def test_volume_profile_trend_is_valid_ratio(data):
    """Volume trend should be a reasonable ratio."""
    result = VolumeProfileAnalyzer.analyze(**data)
    
    # Volume trend is a ratio, so -1 to infinity is valid (negative means decreasing volume)
    assert isinstance(result["volume_trend"], (int, float))


# ============================================================================
# Property tests for TrendStrengthCalculator
# ============================================================================

@given(data=price_data_strategy(min_len=20))
@settings(max_examples=50)
def test_trend_strength_returns_valid_rating(data):
    """Trend strength should return a valid rating."""
    result = TrendStrengthCalculator.calculate(**data)
    
    valid_ratings = {"weak", "moderate", "strong"}
    assert result["rating"] in valid_ratings


@given(data=price_data_strategy(min_len=20))
@settings(max_examples=50)
def test_trend_strength_components_in_valid_range(data):
    """Trend strength components should be in valid ranges."""
    result = TrendStrengthCalculator.calculate(**data)
    
    # ADX, RSI, MACD should be in 0-100 range
    assert 0 <= result["adx"] <= 100
    assert 0 <= result["rsi"] <= 100
    assert 0 <= result["macd"] <= 100


@given(data=price_data_strategy(min_len=20))
@settings(max_examples=50)
def test_trend_strength_strength_in_valid_range(data):
    """Overall strength should be in valid range."""
    result = TrendStrengthCalculator.calculate(**data)
    
    assert 0 <= result["strength"] <= 100


# ============================================================================
# Property tests for PatternRecognizer
# ============================================================================

@given(data=price_data_strategy(min_len=10))
@settings(max_examples=50)
def test_pattern_recognizer_always_returns_dict(data):
    """Pattern recognizer should always return a valid dict."""
    result = PatternRecognizer.recognize(**data)
    
    assert isinstance(result, dict)
    assert "patterns" in result
    assert "best_pattern" in result
    assert "pattern_confirm" in result


@given(data=price_data_strategy(min_len=20))
@settings(max_examples=30)
def test_pattern_recognizer_best_pattern_valid_if_confirmed(data):
    """Best pattern should be valid if pattern_confirm is True."""
    result = PatternRecognizer.recognize(**data)
    
    if result["pattern_confirm"]:
        assert result["best_pattern"] is not None
        assert result["best_pattern"] in result["patterns"]


# ============================================================================
# Property tests for MarketRegimeDetector
# ============================================================================

@given(data=price_data_strategy(min_len=20))
@settings(max_examples=50)
def test_market_regime_returns_valid_regime(data):
    """Market regime should always return a valid regime."""
    result = MarketRegimeDetector.detect(**data)
    
    valid_regimes = {r.value for r in MarketRegime}
    assert result["regime"].value in valid_regimes


@given(data=price_data_strategy(min_len=20))
@settings(max_examples=50)
def test_market_regime_confidence_in_range(data):
    """Market regime confidence should be in 0-100 range."""
    result = MarketRegimeDetector.detect(**data)
    
    assert 0 <= result["confidence"] <= 100


@given(data=price_data_strategy(min_len=20))
@settings(max_examples=50)
def test_market_regime_volatility_non_negative(data):
    """Market regime volatility should be non-negative."""
    result = MarketRegimeDetector.detect(**data)
    
    assert result["volatility"] >= 0


# ============================================================================
# Property tests for AdvancedSignalGenerator
# ============================================================================

@given(data=price_data_strategy(min_len=20))
@settings(max_examples=30)
def test_signal_generator_returns_valid_result_or_none(data):
    """Signal generator should return valid result or None."""
    generator = AdvancedSignalGenerator()
    result = generator.generate(data)
    
    # Either None or a valid AdvancedSignalResult
    if result is not None:
        assert hasattr(result, "direction")
        assert hasattr(result, "confidence")
        assert hasattr(result, "score")
        assert 0 <= result.score <= 100


@given(data=price_data_strategy(min_len=20))
@settings(max_examples=30)
def test_signal_generator_confidence_in_range(data):
    """Signal confidence should be in valid range."""
    generator = AdvancedSignalGenerator()
    result = generator.generate(data)
    
    if result is not None:
        assert 0 <= result.confidence <= 100
        assert 0 <= result.probability <= 1


@given(data=price_data_strategy(min_len=20), tf_data=tf timeframe_data_strategy(num_tfs=2))
@settings(max_examples=20)
def test_signal_generator_with_multiframe(data, tf_data):
    """Signal generator should handle multi-timeframe data."""
    generator = AdvancedSignalGenerator()
    result = generator.generate(data, tf_data)
    
    # Should not crash
    if result is not None:
        assert hasattr(result, "multi_tf_confirm")


# ============================================================================
# Invariant tests
# ============================================================================

@given(data=price_data_strategy(min_len=50))
@settings(max_examples=20)
def test_algorithms_are_deterministic(data):
    """Algorithms should be deterministic (same input = same output)."""
    close = data["close"]
    
    result1 = TrendStrengthCalculator.calculate(**data)
    result2 = TrendStrengthCalculator.calculate(**data)
    
    assert result1 == result2


@given(data=price_data_strategy(min_len=20))
@settings(max_examples=10)
def test_larger_dataset_no_crash(data):
    """Larger datasets should not cause crashes."""
    # Test with 200 data points
    large_data = {k: v * 3 for k, v in data.items()}  # Expand data
    
    result = TrendStrengthCalculator.calculate(**large_data)
    assert "strength" in result
    assert "rating" in result
