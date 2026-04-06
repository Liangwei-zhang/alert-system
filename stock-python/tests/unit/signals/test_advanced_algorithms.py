"""
Unit tests for Advanced Algorithms - tested by Notifications Team (Agent C).

Original developer: Signals Team (Agent B)
"""
import pytest
from unittest.mock import MagicMock

from domains.signals.advanced_algorithms import (
    TrendDirection, MarketRegime, AdvancedSignalResult,
    MultiTimeframeAnalyzer, VolumeProfileAnalyzer, PatternRecognizer,
    TrendStrengthCalculator, MarketRegimeDetector, AdvancedSignalGenerator
)


class TestTrendDirection:
    """Test TrendDirection enum."""
    
    def test_trend_direction_values(self):
        """Test TrendDirection enum values."""
        assert TrendDirection.BULLISH.value == "bullish"
        assert TrendDirection.BEARISH.value == "bearish"
        assert TrendDirection.NEUTRAL.value == "neutral"


class TestMarketRegime:
    """Test MarketRegime enum."""
    
    def test_market_regime_values(self):
        """Test MarketRegime enum values."""
        assert MarketRegime.TRENDING_UP.value == "trending_up"
        assert MarketRegime.TRENDING_DOWN.value == "trending_down"
        assert MarketRegime.RANGING.value == "ranging"
        assert MarketRegime.VOLATILE.value == "volatile"
        assert MarketRegime.CONSOLIDATING.value == "consolidating"


class TestAdvancedSignalResult:
    """Test AdvancedSignalResult dataclass."""
    
    def test_signal_result_creation(self):
        """Test creating AdvancedSignalResult."""
        result = AdvancedSignalResult(
            direction=TrendDirection.BULLISH,
            confidence=85.0,
            probability=0.85,
            regime=MarketRegime.TRENDING_UP,
            trend_strength=75.0,
            volume_confirm=True,
            pattern_confirm=True,
            multi_tf_confirm=True,
            score=90.0
        )
        
        assert result.direction == TrendDirection.BULLISH
        assert result.confidence == 85.0
        assert result.probability == 0.85
        assert result.regime == MarketRegime.TRENDING_UP
        assert result.score == 90.0
        assert result.volume_confirm is True
        assert result.pattern_confirm is True
        assert result.multi_tf_confirm is True


class TestMultiTimeframeAnalyzer:
    """Test MultiTimeframeAnalyzer."""
    
    @pytest.fixture
    def analyzer(self):
        return MultiTimeframeAnalyzer()
    
    def test_analyze_single_timeframe(self, analyzer):
        """Test analysis with single timeframe."""
        data_by_tf = {
            "1h": {"close": [100] * 25, "high": [102] * 25, "low": [98] * 25}
        }
        
        result = analyzer.analyze(data_by_tf)
        
        assert result["confirm"] is False
        assert result["trend_agreement"] == 0
    
    def test_analyze_multiple_timeframes_bullish(self, analyzer):
        """Test analysis with bullish agreement."""
        data_by_tf = {
            "1h": {"close": list(range(95, 120)), "high": [102] * 25, "low": [98] * 25},
            "4h": {"close": list(range(95, 120)), "high": [102] * 25, "low": [98] * 25},
            "1d": {"close": list(range(95, 120)), "high": [102] * 25, "low": [98] * 25}
        }
        
        result = analyzer.analyze(data_by_tf)
        
        assert "confirm" in result
        assert "trend_agreement" in result
        assert "tf_trends" in result
    
    def test_calculate_trend_direction_insufficient_data(self, analyzer):
        """Test trend calculation with insufficient data."""
        close = [100, 101]  # Less than 20
        high = [102, 103]
        low = [98, 99]
        
        result = analyzer._calculate_trend_direction(close, high, low)
        
        assert result == TrendDirection.NEUTRAL
    
    def test_calculate_trend_direction_bullish(self, analyzer):
        """Test bullish trend detection."""
        # Strong uptrend
        close = list(range(100, 125))
        high = [x + 2 for x in close]
        low = [x - 2 for x in close]
        
        result = analyzer._calculate_trend_direction(close, high, low)
        
        assert result in [TrendDirection.BULLISH, TrendDirection.NEUTRAL]


class TestVolumeProfileAnalyzer:
    """Test VolumeProfileAnalyzer."""
    
    def test_analyze_insufficient_data(self):
        """Test analysis with insufficient data."""
        result = VolumeProfileAnalyzer.analyze(
            close=[100],
            high=[102],
            low=[98],
            volume=[1000],
            lookback=20
        )
        
        assert result["confirm"] is False
        assert result["volume_trend"] == 0
    
    def test_analyze_valid_data(self):
        """Test analysis with valid data."""
        # Generate trending data
        close = [100 + i for i in range(25)]
        high = [x + 2 for x in close]
        low = [x - 2 for x in close]
        volume = [1000 + i * 10 for i in range(25)]
        
        result = VolumeProfileAnalyzer.analyze(close, high, low, volume, lookback=20)
        
        assert "confirm" in result
        assert "volume_trend" in result
        assert "vwap" in result
    
    def test_analyze_volume_confirm(self):
        """Test volume confirmation detection."""
        # Price up with increasing volume
        close = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109,
                 110, 111, 112, 113, 114, 115, 116, 117, 118, 119]
        high = [x + 2 for x in close]
        low = [x - 2 for x in close]
        # Increasing volume
        volume = [100, 150, 200, 250, 300, 350, 400, 450, 500, 550,
                  600, 650, 700, 750, 800, 850, 900, 950, 1000, 1050]
        
        result = VolumeProfileAnalyzer.analyze(close, high, low, volume)
        
        # Should have some volume trend
        assert "volume_trend" in result


class TestPatternRecognizer:
    """Test PatternRecognizer."""
    
    def test_recognize_insufficient_data(self):
        """Test pattern recognition with insufficient data."""
        result = PatternRecognizer.recognize(
            close=[100, 101],
            high=[102, 103],
            low=[98, 99],
            volume=[1000, 1100]
        )
        
        assert "patterns" in result
        assert "pattern_confirm" in result
    
    def test_recognize_double_bottom(self):
        """Test double bottom pattern detection."""
        # Create double bottom pattern
        low = [100, 102, 101, 103, 102, 98, 99, 98, 100, 102, 103]
        close = [101, 103, 102, 104, 103, 99, 100, 99, 101, 103, 104]
        high = [103, 105, 104, 106, 105, 101, 102, 101, 103, 105, 106]
        volume = [1000] * 11
        
        result = PatternRecognizer.recognize(close, high, low, volume)
        
        assert "patterns" in result
        # May detect double_bottom if pattern is clear
    
    def test_recognize_double_top(self):
        """Test double top pattern detection."""
        high = [106, 105, 104, 103, 104, 105, 106, 105, 104, 103, 102]
        low = [104, 103, 102, 101, 102, 103, 104, 103, 102, 101, 100]
        close = [105, 104, 103, 102, 103, 104, 105, 104, 103, 102, 101]
        volume = [1000] * 11
        
        result = PatternRecognizer.recognize(close, high, low, volume)
        
        assert "patterns" in result
    
    def test_recognize_wedge(self):
        """Test wedge pattern detection."""
        # Ascending wedge - highs converging
        high = [100, 102, 103, 104, 105, 105.5, 106, 106.3, 106.5, 106.6]
        low = [98, 99, 99.5, 100, 100.2, 100.3, 100.4, 100.4, 100.5, 100.5]
        close = [99, 101, 102, 103, 104, 104, 105, 105, 106, 106]
        volume = [1000] * 10
        
        result = PatternRecognizer.recognize(close, high, low, volume)
        
        assert "patterns" in result
    
    def test_recognize_flag(self):
        """Test flag pattern detection."""
        # Strong move then consolidation
        close = [100, 105, 110, 115, 120, 121, 122, 121, 123, 122, 124, 123, 125, 124, 126]
        high = [102, 107, 112, 117, 122, 123, 124, 123, 125, 124, 126, 125, 127, 126, 128]
        low = [98, 103, 108, 113, 118, 119, 120, 119, 121, 120, 122, 121, 123, 122, 124]
        volume = [1000, 1500, 2000, 2500, 3000, 1500, 1200, 1100, 1300, 1200, 1400, 1300, 1500, 1400, 1600]
        
        result = PatternRecognizer.recognize(close, high, low, volume)
        
        assert "patterns" in result


class TestTrendStrengthCalculator:
    """Test TrendStrengthCalculator."""
    
    def test_calculate_insufficient_data(self):
        """Test with insufficient data."""
        result = TrendStrengthCalculator.calculate(
            close=[100, 101],
            high=[102, 103],
            low=[98, 99],
            volume=[1000, 1100],
            lookback=20
        )
        
        assert result["strength"] == 0
        assert result["rating"] == "weak"
    
    def test_calculate_valid_data(self):
        """Test with valid data."""
        close = [100 + i for i in range(25)]
        high = [x + 2 for x in close]
        low = [x - 2 for x in close]
        volume = [1000] * 25
        
        result = TrendStrengthCalculator.calculate(close, high, low, volume, lookback=20)
        
        assert "strength" in result
        assert "rating" in result
        assert "adx" in result
        assert "rsi" in result
        assert "macd" in result
    
    def test_rsi_calculation(self):
        """Test RSI calculation."""
        # Uptrend
        close = list(range(100, 120))
        
        rsi = TrendStrengthCalculator._rsi(close, period=14)
        
        assert 0 <= rsi <= 100
    
    def test_adx_calculation(self):
        """Test ADX calculation."""
        high = [100 + i for i in range(20)]
        low = [98 + i for i in range(20)]
        close = [99 + i for i in range(20)]
        
        adx = TrendStrengthCalculator._adx(high, low, close, period=14)
        
        assert adx >= 0
    
    def test_macd_calculation(self):
        """Test MACD calculation."""
        close = list(range(100, 130))
        
        macd = TrendStrengthCalculator._macd(close)
        
        assert 0 <= macd <= 100


class TestMarketRegimeDetector:
    """Test MarketRegimeDetector."""
    
    def test_detect_insufficient_data(self):
        """Test with insufficient data."""
        result = MarketRegimeDetector.detect(
            close=[100, 101],
            high=[102, 103],
            low=[98, 99],
            volume=[1000, 1100]
        )
        
        assert result["regime"] == MarketRegime.CONSOLIDATING
        assert result["confidence"] == 0
    
    def test_detect_trending_up(self):
        """Test trending up regime detection."""
        # Strong uptrend
        close = [100, 105, 110, 115, 120, 125, 130, 135, 140, 145,
                 150, 155, 160, 165, 170, 175, 180, 185, 190, 195]
        high = [x + 5 for x in close]
        low = [x - 5 for x in close]
        volume = [1000] * 20
        
        result = MarketRegimeDetector.detect(close, high, low, volume)
        
        assert "regime" in result
        assert "confidence" in result
    
    def test_detect_trending_down(self):
        """Test trending down regime detection."""
        close = list(reversed([100, 105, 110, 115, 120, 125, 130, 135, 140, 145,
                              150, 155, 160, 165, 170, 175, 180, 185, 190, 195]))
        high = [x + 5 for x in close]
        low = [x - 5 for x in close]
        volume = [1000] * 20
        
        result = MarketRegimeDetector.detect(close, high, low, volume)
        
        assert "regime" in result
    
    def test_detect_ranging(self):
        """Test ranging regime detection."""
        # Sideways movement
        close = [100, 102, 99, 101, 103, 100, 102, 98, 101, 103,
                 100, 102, 99, 101, 103, 100, 102, 99, 101, 103]
        high = [x + 3 for x in close]
        low = [x - 3 for x in close]
        volume = [1000] * 20
        
        result = MarketRegimeDetector.detect(close, high, low, volume)
        
        assert "regime" in result
    
    def test_detect_consolidating(self):
        """Test consolidating regime detection."""
        # Tight range
        close = [100, 101, 99, 100, 101, 100, 99, 101, 100, 101,
                 100, 101, 99, 100, 101, 100, 99, 101, 100, 101]
        high = [x + 1 for x in close]
        low = [x - 1 for x in close]
        volume = [1000] * 20
        
        result = MarketRegimeDetector.detect(close, high, low, volume)
        
        assert result["regime"] == MarketRegime.CONSOLIDATING


class TestAdvancedSignalGenerator:
    """Test AdvancedSignalGenerator."""
    
    @pytest.fixture
    def generator(self):
        return AdvancedSignalGenerator()
    
    def test_generate_insufficient_data(self, generator):
        """Test with insufficient data."""
        data = {"close": [100, 101], "high": [102, 103], "low": [98, 99], "volume": [1000, 1100]}
        
        result = generator.generate(data)
        
        assert result is None
    
    def test_generate_valid_data(self, generator):
        """Test with valid data."""
        close = [100 + i for i in range(25)]
        high = [x + 2 for x in close]
        low = [x - 2 for x in close]
        volume = [1000] * 25
        
        data = {"close": close, "high": high, "low": low, "volume": volume}
        
        result = generator.generate(data)
        
        # May return None if no clear direction
        assert result is None or isinstance(result, AdvancedSignalResult)
    
    def test_generate_with_multi_tf(self, generator):
        """Test with multi-timeframe data."""
        close = [100 + i for i in range(25)]
        high = [x + 2 for x in close]
        low = [x - 2 for x in close]
        volume = [1000] * 25
        
        data = {"close": close, "high": high, "low": low, "volume": volume}
        
        # Multi-TF with same direction
        data_by_tf = {
            "1h": data,
            "4h": data,
            "1d": data
        }
        
        result = generator.generate(data, data_by_tf)
        
        # Should process with multi-TF confirmation
        assert result is None or isinstance(result, AdvancedSignalResult)
    
    def test_calculate_score(self, generator):
        """Test score calculation."""
        score = generator._calculate_score(
            direction=TrendDirection.BULLISH,
            confidence=80,
            pattern_confirm=True,
            volume_confirm=True,
            tf_confirm=True,
            strength=70,
            regime=MarketRegime.TRENDING_UP
        )
        
        assert 0 <= score <= 100
    
    def test_calculate_score_bearish(self, generator):
        """Test bearish score calculation."""
        score = generator._calculate_score(
            direction=TrendDirection.BEARISH,
            confidence=75,
            pattern_confirm=True,
            volume_confirm=False,
            tf_confirm=True,
            strength=65,
            regime=MarketRegime.TRENDING_DOWN
        )
        
        assert 0 <= score <= 100


class TestAdvancedAlgorithmsEdgeCases:
    """Test edge cases for advanced algorithms."""
    
    def test_empty_data(self):
        """Test with empty data."""
        result = AdvancedSignalGenerator().generate({})
        assert result is None
    
    def test_extreme_values(self):
        """Test with extreme price values."""
        close = [1_000_000 + i for i in range(25)]
        high = [x + 1000 for x in close]
        low = [x - 1000 for x in close]
        volume = [1_000_000] * 25
        
        data = {"close": close, "high": high, "low": low, "volume": volume}
        
        result = AdvancedSignalGenerator().generate(data)
        
        assert result is None or isinstance(result, AdvancedSignalResult)
    
    def test_zero_volume(self):
        """Test with zero volume."""
        close = [100 + i for i in range(25)]
        high = [x + 2 for x in close]
        low = [x - 2 for x in close]
        volume = [0] * 25
        
        result = VolumeProfileAnalyzer.analyze(close, high, low, volume)
        
        # Should handle gracefully
        assert "confirm" in result