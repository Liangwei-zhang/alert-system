"""
Advanced signal algorithms - Gen 3.2+ sophisticated signal detection.

Features:
- Multi-timeframe confirmations
- Volume-weighted price action
- Trend strength calculations
- Advanced pattern recognition
- Market structure analysis
"""
import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
from scipy import stats


class TrendDirection(str, Enum):
    """Trend direction."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class MarketRegime(str, Enum):
    """Market regime classification."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    CONSOLIDATING = "consolidating"


@dataclass
class AdvancedSignalResult:
    """Advanced signal result."""
    direction: TrendDirection
    confidence: float
    probability: float
    regime: MarketRegime
    trend_strength: float
    volume_confirm: bool
    pattern_confirm: bool
    multi_tf_confirm: bool
    score: float  # Combined score (0-100)


class MultiTimeframeAnalyzer:
    """Multi-timeframe analysis for signal confirmation."""
    
    def __init__(self):
        self.timeframes = ["1h", "4h", "1d"]  # Default TF hierarchy
    
    def analyze(
        self,
        data_by_tf: dict[str, dict]
    ) -> dict[str, any]:
        """
        Analyze multiple timeframes for confirmation.
        
        Args:
            data_by_tf: Dict mapping timeframe to OHLCV data
            
        Returns:
            Dict with multi-TF analysis results
        """
        if len(data_by_tf) < 2:
            return {"confirm": False, "trend_agreement": 0}
        
        # Analyze each timeframe
        tf_trends = {}
        for tf, data in data_by_tf.items():
            if "close" in data and len(data["close"]) >= 20:
                trend = self._calculate_trend_direction(
                    data["close"], data.get("high", []), data.get("low", [])
                )
                tf_trends[tf] = trend
        
        # Check trend agreement
        if len(tf_trends) < 2:
            return {"confirm": False, "trend_agreement": 0}
        
        # Count agreement
        bullish_count = sum(1 for t in tf_trends.values() if t == TrendDirection.BULLISH)
        bearish_count = sum(1 for t in tf_trends.values() if t == TrendDirection.BEARISH)
        
        total = len(tf_trends)
        agreement = max(bullish_count, bearish_count) / total
        
        # Bullish confirmation: higher TFs agree on bullish
        confirm = agreement >= 0.66  # At least 2/3 agree
        
        return {
            "confirm": confirm,
            "trend_agreement": agreement,
            "tf_trends": tf_trends,
            "dominant_direction": (
                TrendDirection.BULLISH if bullish_count > bearish_count 
                else TrendDirection.BEARISH if bearish_count > bullish_count
                else TrendDirection.NEUTRAL
            )
        }
    
    def _calculate_trend_direction(
        self, 
        close: list, 
        high: list, 
        low: list
    ) -> TrendDirection:
        """Calculate trend direction from price data."""
        if len(close) < 20:
            return TrendDirection.NEUTRAL
        
        # Use linear regression for trend
        x = np.arange(len(close))
        slope, _, _, _, _ = stats.linregress(x, close[-20:])
        
        # Normalize slope by price
        avg_price = np.mean(close[-20:])
        normalized_slope = (slope / avg_price) * 100
        
        if normalized_slope > 0.5:
            return TrendDirection.BULLISH
        elif normalized_slope < -0.5:
            return TrendDirection.BEARISH
        return TrendDirection.NEUTRAL


class VolumeProfileAnalyzer:
    """Volume-weighted price action analysis."""
    
    @staticmethod
    def analyze(
        close: list,
        high: list,
        low: list,
        volume: list,
        lookback: int = 20
    ) -> dict:
        """
        Analyze volume-weighted price action.
        
        Returns:
            Dict with volume analysis results
        """
        if len(close) < lookback or len(volume) < lookback:
            return {
                "confirm": False,
                "volume_trend": 0,
                "Volume_Weight": 0
            }
        
        recent_close = close[-lookback:]
        recent_volume = volume[-lookback:]
        
        # Calculate volume-weighted price change
        vwap = np.average(recent_close, weights=recent_volume)
        
        # Volume trend (increasing/decreasing)
        first_half_vol = np.mean(recent_volume[:lookback//2])
        second_half_vol = np.mean(recent_volume[lookback//2:])
        volume_trend = (second_half_vol / first_half_vol) - 1 if first_half_vol > 0 else 0
        
        # Price vs VWAP
        current_price = close[-1]
        price_vs_vwap = (current_price - vwap) / vwap if vwap > 0 else 0
        
        # Volume confirmation: higher volume on price movement direction
        price_change = close[-1] - close[-lookback]
        direction = 1 if price_change > 0 else -1
        
        # Recent price moves with volume
        weighted_direction = 0
        for i in range(1, lookback):
            price_move = close[-i] - close[-i-1]
            if (price_move > 0 and direction > 0) or (price_move < 0 and direction < 0):
                weighted_direction += recent_volume[i]
        
        total_volume = np.sum(recent_volume)
        confirm = (weighted_direction / total_volume) > 0.5 if total_volume > 0 else False
        
        return {
            "confirm": confirm,
            "volume_trend": round(volume_trend, 3),
            "vwap": round(vwap, 4),
            "price_vs_vwap": round(price_vs_vwap, 3),
            "weighted_direction_ratio": round(
                weighted_direction / total_volume, 3
            ) if total_volume > 0 else 0
        }


class PatternRecognizer:
    """Advanced pattern recognition."""
    
    @staticmethod
    def recognize(
        close: list,
        high: list,
        low: list,
        volume: list
    ) -> dict:
        """
        Recognize chart patterns.
        
        Returns:
            Dict with pattern results
        """
        patterns = {}
        
        if len(close) >= 20:
            # Double bottom/bottom
            patterns["double_bottom"] = PatternRecognizer._double_bottom(low, close)
            patterns["double_top"] = PatternRecognizer._double_top(high, close)
        
        if len(close) >= 10:
            # Ascending/descending wedge
            patterns["wedge"] = PatternRecognizer._wedge(high, low)
        
        if len(close) >= 15:
            # Bullish/bearish flag
            patterns["flag"] = PatternRecognizer._flag(close, high, low)
        
        # Return best pattern
        valid_patterns = {k: v for k, v in patterns.items() if v["detected"]}
        
        return {
            "patterns": valid_patterns,
            "best_pattern": max(valid_patterns.items(), 
                                key=lambda x: x[1]["confidence"])[0] 
                               if valid_patterns else None,
            "pattern_confirm": len(valid_patterns) > 0
        }
    
    @staticmethod
    def _double_bottom(low: list, close: list) -> dict:
        """Detect double bottom pattern."""
        if len(low) < 10:
            return {"detected": False, "confidence": 0}
        
        # Find recent lows
        lows = []
        for i in range(1, len(low) - 1):
            if low[i] < low[i-1] and low[i] < low[i+1]:
                lows.append((i, low[i]))
        
        if len(lows) < 2:
            return {"detected": False, "confidence": 0}
        
        # Check for two similar lows
        last_low_idx, last_low = lows[-1]
        prev_low_idx, prev_low = lows[-2]
        
        # Within 2% tolerance
        if abs(last_low - prev_low) / prev_low < 0.02:
            # Second low should be higher (recovery)
            if last_low >= prev_low and close[-1] > close[prev_low_idx]:
                return {
                    "detected": True,
                    "confidence": 70,
                    "target": last_low * 1.05
                }
        
        return {"detected": False, "confidence": 0}
    
    @staticmethod
    def _double_top(high: list, close: list) -> dict:
        """Detect double top pattern."""
        if len(high) < 10:
            return {"detected": False, "confidence": 0}
        
        highs = []
        for i in range(1, len(high) - 1):
            if high[i] > high[i-1] and high[i] > high[i+1]:
                highs.append((i, high[i]))
        
        if len(highs) < 2:
            return {"detected": False, "confidence": 0}
        
        last_high_idx, last_high = highs[-1]
        prev_high_idx, prev_high = highs[-2]
        
        if abs(last_high - prev_high) / prev_high < 0.02:
            if last_high <= prev_high and close[-1] < close[prev_high_idx]:
                return {
                    "detected": True,
                    "confidence": 70,
                    "target": last_high * 0.95
                }
        
        return {"detected": False, "confidence": 0}
    
    @staticmethod
    def _wedge(high: list, low: list) -> dict:
        """Detect wedge pattern."""
        if len(high) < 10 or len(low) < 10:
            return {"detected": False, "confidence": 0}
        
        # Linear regression on highs and lows
        x = np.arange(10)
        
        high_recent = high[-10:]
        low_recent = low[-10:]
        
        slope_high, _, _, _, _ = stats.linregress(x, high_recent)
        slope_low, _, _, _, _ = stats.linregress(x, low_recent)
        
        # Converging wedges (both slopes same direction but different magnitude)
        if slope_high > 0 and slope_low > 0:
            if slope_low < slope_high:  # Ascending wedge (bullish)
                return {"detected": True, "type": "ascending", "confidence": 65}
        
        if slope_high < 0 and slope_low < 0:
            if slope_low > slope_high:  # Descending wedge (bearish)
                return {"detected": True, "type": "descending", "confidence": 65}
        
        return {"detected": False, "confidence": 0}
    
    @staticmethod
    def _flag(close: list, high: list, low: list) -> dict:
        """Detect flag pattern."""
        if len(close) < 15:
            return {"detected": False, "confidence": 0}
        
        # Strong move followed by consolidation
        first_move = np.mean(close[-15:-10]) - np.mean(close[-20:-15])
        consolidation = np.std(close[-10:])
        consolidation_range = np.max(high[-10:]) - np.min(low[-10:])
        
        # Flag: strong move then tight consolidation
        if abs(first_move) > consolidation_range * 2:
            if consolidation < consolidation_range * 0.5:
                direction = "bullish" if first_move > 0 else "bearish"
                return {
                    "detected": True,
                    "type": direction,
                    "confidence": 60
                }
        
        return {"detected": False, "confidence": 0}


class TrendStrengthCalculator:
    """Calculate trend strength using multiple indicators."""
    
    @staticmethod
    def calculate(
        close: list,
        high: list,
        low: list,
        volume: list,
        lookback: int = 20
    ) -> dict:
        """
        Calculate trend strength using multiple methods.
        
        Returns:
            Dict with trend strength metrics
        """
        if len(close) < lookback:
            return {"strength": 0, "rating": "weak"}
        
        # ADX calculation
        adx = TrendStrengthCalculator._adx(high, low, close, lookback)
        
        # RSI
        rsi = TrendStrengthCalculator._rsi(close, lookback)
        
        # MACD
        macd = TrendStrengthCalculator._macd(close)
        
        # Combine into strength score
        strength = (adx * 0.4 + rsi * 0.3 + macd * 0.3)
        
        rating = "strong" if strength > 70 else "moderate" if strength > 40 else "weak"
        
        return {
            "strength": round(strength, 1),
            "rating": rating,
            "adx": round(adx, 1),
            "rsi": round(rsi, 1),
            "macd": round(macd, 1)
        }
    
    @staticmethod
    def _adx(high: list, low: list, close: list, period: int = 14) -> float:
        """Calculate ADX."""
        if len(high) < period + 1:
            return 0
        
        # Calculate +DM and -DM
        plus_dm = []
        minus_dm = []
        tr = []
        
        for i in range(1, len(high)):
            high_diff = high[i] - high[i-1]
            low_diff = low[i-1] - low[i]
            
            plus_dm.append(high_diff if high_diff > low_diff and high_diff > 0 else 0)
            minus_dm.append(low_diff if low_diff > high_diff and low_diff > 0 else 0)
            
            tr.append(max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            ))
        
        # Smoothed values
        plus_di = np.mean(plus_dm[-period:])
        minus_di = np.mean(minus_dm[-period:])
        tr_avg = np.mean(tr[-period:])
        
        if tr_avg == 0:
            return 0
        
        plus_di = (plus_di / tr_avg) * 100
        minus_di = (minus_di / tr_avg) * 100
        
        di_sum = plus_di + minus_di
        if di_sum == 0:
            return 0
        
        dx = (abs(plus_di - minus_di) / di_sum) * 100
        
        return dx / 1  # Simplified ADX
    
    @staticmethod
    def _rsi(close: list, period: int = 14) -> float:
        """Calculate RSI."""
        if len(close) < period + 1:
            return 50
        
        deltas = np.diff(close[-period-1:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def _macd(close: list) -> float:
        """Calculate MACD signal."""
        if len(close) < 26:
            return 50
        
        # EMA calculations
        ema_12 = np.mean(close[-12:])  # Simplified
        ema_26 = np.mean(close[-26:])
        
        macd_line = ema_12 - ema_26
        signal_line = np.mean(close[-9:])  # Simplified signal
        
        macd_histogram = macd_line - signal_line
        
        # Normalize to 0-100
        normalized = 50 + (macd_histogram / close[-1]) * 1000
        
        return max(0, min(100, normalized))


class MarketRegimeDetector:
    """Detect current market regime."""
    
    @staticmethod
    def detect(
        close: list,
        high: list,
        low: list,
        volume: list
    ) -> dict:
        """
        Detect market regime.
        
        Returns:
            Dict with regime classification
        """
        if len(close) < 20:
            return {"regime": MarketRegime.CONSOLIDATING, "confidence": 0}
        
        # Calculate volatility
        returns = np.diff(close[-20:]) / close[-20:-1]
        volatility = np.std(returns) * 100
        
        # Calculate trend
        x = np.arange(20)
        slope, _, r_value, _, _ = stats.linregress(x, close[-20:])
        avg_price = np.mean(close[-20:])
        normalized_slope = (slope / avg_price) * 100
        
        r_squared = r_value ** 2
        
        # Range estimation
        range_pct = (max(close[-20:]) - min(close[-20:])) / avg_price
        
        # Classify regime
        if r_squared > 0.7:  # Strong trend
            if normalized_slope > 0.5:
                regime = MarketRegime.TRENDING_UP
            else:
                regime = MarketRegime.TRENDING_DOWN
        elif volatility > 3:  # High volatility
            regime = MarketRegime.VOLATILE
        elif range_pct < 0.02:  # Tight range
            regime = MarketRegime.CONSOLIDATING
        else:
            regime = MarketRegime.RANGING
        
        return {
            "regime": regime,
            "confidence": round(r_squared * 100, 1),
            "volatility": round(volatility, 2),
            "trend_slope": round(normalized_slope, 3)
        }


class AdvancedSignalGenerator:
    """Advanced signal generation using all algorithms."""
    
    def __init__(self):
        self.tf_analyzer = MultiTimeframeAnalyzer()
        self.volume_analyzer = VolumeProfileAnalyzer()
        self.pattern_recognizer = PatternRecognizer()
        self.trend_strength = TrendStrengthCalculator()
        self.regime_detector = MarketRegimeDetector()
    
    def generate(
        self,
        data: dict,
        data_by_tf: Optional[dict] = None
    ) -> Optional[AdvancedSignalResult]:
        """
        Generate advanced signal.
        
        Args:
            data: Dict with 'close', 'high', 'low', 'volume' lists
            data_by_tf: Optional dict of timeframe -> data
            
        Returns:
            AdvancedSignalResult or None
        """
        close = data.get("close", [])
        high = data.get("high", [])
        low = data.get("low", [])
        volume = data.get("volume", [])
        
        if len(close) < 20:
            return None
        
        # Run all analyses
        pattern_result = self.pattern_recognizer.recognize(close, high, low, volume)
        volume_result = self.volume_analyzer.analyze(close, high, low, volume)
        strength_result = self.trend_strength.calculate(close, high, low, volume)
        regime_result = self.regime_detector.detect(close, high, low, volume)
        
        # Multi-TF if available
        tf_result = {"confirm": True, "dominant_direction": TrendDirection.NEUTRAL}
        if data_by_tf and len(data_by_tf) >= 2:
            tf_result = self.tf_analyzer.analyze(data_by_tf)
        
        # Determine direction from multiple signals
        bullish_signals = 0
        bearish_signals = 0
        
        if volume_result.get("confirm"):
            bullish_signals += 1
        
        if pattern_result.get("pattern_confirm"):
            pattern_direction = pattern_result.get("best_pattern", "")
            if "bottom" in pattern_direction or pattern_result.get("patterns", {}).get("flag", {}).get("type") == "bullish":
                bullish_signals += 1
            elif "top" in pattern_direction or pattern_result.get("patterns", {}).get("flag", {}).get("type") == "bearish":
                bearish_signals += 1
        
        if strength_result.get("strength", 0) > 50:
            if strength_result.get("rsi", 50) < 40:
                bullish_signals += 1
            elif strength_result.get("rsi", 50) > 60:
                bearish_signals += 1
        
        if tf_result.get("confirm"):
            if tf_result.get("dominant_direction") == TrendDirection.BULLISH:
                bullish_signals += 1
            elif tf_result.get("dominant_direction") == TrendDirection.BEARISH:
                bearish_signals += 1
        
        # Determine final direction
        if bullish_signals > bearish_signals:
            direction = TrendDirection.BULLISH
            confidence = min(bullish_signals * 20 + 30, 95)
        elif bearish_signals > bullish_signals:
            direction = TrendDirection.BEARISH
            confidence = min(bearish_signals * 20 + 30, 95)
        else:
            return None  # No clear direction
        
        # Calculate probability
        probability = confidence / 100
        
        # Calculate final score
        score = self._calculate_score(
            direction=direction,
            confidence=confidence,
            pattern_confirm=pattern_result.get("pattern_confirm", False),
            volume_confirm=volume_result.get("confirm", False),
            tf_confirm=tf_result.get("confirm", False),
            strength=strength_result.get("strength", 0),
            regime=regime_result.get("regime", MarketRegime.RANGING)
        )
        
        return AdvancedSignalResult(
            direction=direction,
            confidence=confidence,
            probability=probability,
            regime=regime_result.get("regime", MarketRegime.RANGING),
            trend_strength=strength_result.get("strength", 0),
            volume_confirm=volume_result.get("confirm", False),
            pattern_confirm=pattern_result.get("pattern_confirm", False),
            multi_tf_confirm=tf_result.get("confirm", False),
            score=score
        )
    
    def _calculate_score(
        self,
        direction: TrendDirection,
        confidence: float,
        pattern_confirm: bool,
        volume_confirm: bool,
        tf_confirm: bool,
        strength: float,
        regime: MarketRegime
    ) -> float:
        """Calculate overall signal score."""
        score = confidence * 0.3
        
        # Confirmation bonuses
        if pattern_confirm:
            score += 15
        if volume_confirm:
            score += 10
        if tf_confirm:
            score += 15
        
        # Trend strength
        score += strength * 0.15
        
        # Regime adjustment (favor trending, penalize ranging)
        if regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
            score += 10
        elif regime == MarketRegime.RANGING:
            score -= 10
        
        return min(100, max(0, score))