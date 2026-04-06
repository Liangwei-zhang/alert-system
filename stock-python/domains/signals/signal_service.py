"""
Signal service - Gen 3.1 algorithm implementation.

Features:
- Three-layer validation (SFP + CHOCH + FVG)
- Sigmoid probability calculation
- ATR dynamic thresholds
- Support for buy/sell/split-buy/split-sell signals
"""
import json
import math
from datetime import datetime
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from domains.signals.signal import (
    Signal, SignalType, SignalStatus, SignalValidation,
    SignalAlert
)
from domains.search.stock import Stock


class ATRCalculator:
    """ATR (Average True Range) calculator for dynamic thresholds."""
    
    @staticmethod
    def calculate(high: list, low: list, close: list, period: int = 14) -> float:
        """Calculate ATR value."""
        if len(high) < period + 1:
            return 0.0
        
        tr = []
        for i in range(1, len(high)):
            h_l = high[i] - low[i]
            h_c = abs(high[i] - close[i-1])
            l_c = abs(low[i] - close[i-1])
            tr.append(max(h_l, h_c, l_c))
        
        if len(tr) < period:
            return 0.0
        
        return float(np.mean(tr[-period:]))
    
    @staticmethod
    def calculate_atr_percent(atr: float, price: float) -> float:
        """Calculate ATR as percentage of price."""
        if price == 0:
            return 0.0
        return (atr / price) * 100


class SFPDetector:
    """Smart Money Concept - Smart Fair Pullback detector."""
    
    @staticmethod
    def detect(high: list, low: list, close: list, lookback: int = 10) -> bool:
        """
        Detect Smart Fair Pullback - pullback to institutional order block.
        Returns True if SFP pattern detected.
        """
        if len(high) < lookback + 1:
            return False
        
        # Look for price to pull back to recent supply/demand zone
        recent_highs = high[-lookback:]
        recent_lows = low[-lookback:]
        
        current_close = close[-1]
        current_low = low[-1]
        current_high = high[-1]
        
        # Find swing high and low in lookback period
        swing_high = max(recent_highs[:-1])
        swing_low = min(recent_lows[:-1])
        
        # SFP logic: price pulls back to zone created by institutional move
        # For bullish SFP: price pulls back to recent low zone
        if current_close < close[-2]:  # Price moving down (potential buy setup)
            # Check if current low is near recent low (support zone)
            zone_tolerance = (swing_high - swing_low) * 0.3
            if abs(current_low - swing_low) < zone_tolerance:
                return True
        
        # For bearish SFP: price pulls back to recent high zone
        if current_close > close[-2]:  # Price moving up (potential sell setup)
            zone_tolerance = (swing_high - swing_low) * 0.3
            if abs(current_high - swing_high) < zone_tolerance:
                return True
        
        return False


class CHOCHDetector:
    """Change of Character detector - breakout of structure."""
    
    @staticmethod
    def detect(high: list, low: list, close: list, lookback: int = 5) -> dict:
        """
        Detect Change of Character - break of market structure.
        Returns dict with 'direction' ('bullish' or 'bearish') and 'validated' bool.
        """
        if len(high) < lookback + 1:
            return {"direction": None, "validated": False}
        
        # Find recent swing points
        swing_highs = []
        swing_lows = []
        
        for i in range(1, len(high) - 1):
            if high[i] > high[i-1] and high[i] > high[i+1]:
                swing_highs.append((i, high[i]))
            if low[i] < low[i-1] and low[i] < low[i+1]:
                swing_lows.append((i, low[i]))
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return {"direction": None, "validated": False}
        
        # Most recent swing points
        last_high_idx, last_high = swing_highs[-1]
        last_low_idx, last_low = swing_lows[-1]
        
        # Check for bullish CHOCH: break above recent swing high
        if close[-1] > last_high and last_high_idx > last_low_idx:
            return {"direction": "bullish", "validated": True}
        
        # Check for bearish CHOCH: break below recent swing low
        if close[-1] < last_low and last_low_idx > last_high_idx:
            return {"direction": "bearish", "validated": True}
        
        return {"direction": None, "validated": False}


class FVGDetector:
    """Fair Value Gap detector."""
    
    @staticmethod
    def detect(high: list, low: list, close: list) -> dict:
        """
        Detect Fair Value Gap - momentum gap in price action.
        Returns dict with 'direction', 'gap_size', 'filled' bool.
        """
        if len(high) < 3:
            return {"direction": None, "gap_size": 0, "filled": False, "validated": False}
        
        # FVG: gap between two candles where middle candle's range doesn't overlap
        # Bullish FVG: low of current > high of previous (gap up)
        # Bearish FVG: high of current < low of previous (gap down)
        
        current_low = low[-1]
        current_high = high[-1]
        prev_low = low[-2]
        prev_high = high[-2]
        mid_high = max(high[-3], high[-2])
        mid_low = min(low[-3], low[-2])
        
        # Bullish FVG
        if current_low > mid_high:
            gap_size = current_low - mid_high
            return {
                "direction": "bullish",
                "gap_size": gap_size,
                "filled": current_low <= mid_high,  # Would be filled if price drops
                "validated": True
            }
        
        # Bearish FVG
        if current_high < mid_low:
            gap_size = mid_low - current_high
            return {
                "direction": "bearish",
                "gap_size": gap_size,
                "filled": current_high >= mid_low,
                "validated": True
            }
        
        return {"direction": None, "gap_size": 0, "filled": False, "validated": False}


class SigmoidProbability:
    """Sigmoid probability calculation for signal confidence."""
    
    @staticmethod
    def calculate(validation_count: int, total_validations: int = 3, 
                  base_probability: float = 0.5) -> float:
        """
        Calculate sigmoid probability based on validation layers.
        
        Args:
            validation_count: Number of validated layers (0-3)
            total_validations: Total validation layers (3 for SFP+CHOCH+FVG)
            base_probability: Base probability before sigmoid
            
        Returns:
            Probability between 0 and 1
        """
        # Input to sigmoid: more validations = higher value
        x = (validation_count / total_validations) * 6 - 3  # Range: -3 to 3
        sigmoid = 1 / (1 + math.exp(-x))
        
        # Blend with base probability
        weight = validation_count / total_validations
        return (sigmoid * weight) + (base_probability * (1 - weight))
    
    @staticmethod
    def calculate_with_indicators(validation_count: int, 
                                  indicator_signals: float,
                                  total_validations: int = 3) -> float:
        """
        Calculate probability with additional indicator signals.
        
        Args:
            validation_count: Number of validated layers
            indicator_signals: Indicator confidence (-1 to 1)
            total_validations: Total validation layers
        """
        validation_prob = SigmoidProbability.calculate(
            validation_count, total_validations, base_probability=0.3
        )
        
        # Normalize indicator signals to 0-1 range
        normalized_indicators = (indicator_signals + 1) / 2
        
        # Weighted combination: 70% validation, 30% indicators
        return (validation_prob * 0.7) + (normalized_indicators * 0.3)


class SignalGenerator:
    """Gen 3.1 signal generation algorithm."""
    
    def __init__(self, db: Session):
        self.db = db
        self.atr_calculator = ATRCalculator()
        self.sfp_detector = SFPDetector()
        self.chooch_detector = CHOCHDetector()
        self.fvg_detector = FVGDetector()
        self.sigmoid = SigmoidProbability()
    
    def generate_signal(
        self,
        stock: Stock,
        high: list,
        low: list,
        close: list,
        volume: list,
        strategy_id: Optional[int] = None
    ) -> Optional[Signal]:
        """
        Generate a trading signal using Gen 3.1 algorithm.
        
        Args:
            stock: Stock object
            high: List of high prices
            low: List of low prices
            close: List of close prices
            volume: List of volumes
            strategy_id: Optional strategy ID for filtering
            
        Returns:
            Signal object or None if no signal
        """
        if len(high) < 20 or len(low) < 20 or len(close) < 20:
            return None
        
        current_price = close[-1]
        
        # Calculate ATR for dynamic thresholds
        atr = self.atr_calculator.calculate(high, low, close, period=14)
        atr_percent = self.atr_calculator.calculate_atr_percent(atr, current_price)
        
        # Run validation layers
        sfp_validated = self.sfp_detector.detect(high, low, close)
        chooch_result = self.chooch_detector.detect(high, low, close)
        fvg_result = self.fvg_detector.detect(high, low, close)
        
        chooch_validated = chooch_result["validated"]
        fvg_validated = fvg_result["validated"]
        
        # Determine signal direction
        direction = None
        if chooch_result["direction"] == "bullish" and fvg_result["direction"] == "bullish":
            direction = "bullish"
        elif chooch_result["direction"] == "bearish" and fvg_result["direction"] == "bearish":
            direction = "bearish"
        
        if direction is None:
            return None
        
        # Calculate validation count
        validation_count = sum([sfp_validated, chooch_validated, fvg_validated])
        
        # Calculate probability using sigmoid
        probability = self.sigmoid.calculate(validation_count, total_validations=3)
        
        # Determine confidence based on validation layers + ATR
        confidence = self._calculate_confidence(
            validation_count, atr_percent, direction
        )
        
        # Only generate signal if confidence meets threshold
        if confidence < 50:
            return None
        
        # Determine signal type
        if direction == "bullish":
            signal_type = SignalType.BUY
        else:
            signal_type = SignalType.SELL
        
        # Calculate price levels with ATR
        levels = self._calculate_price_levels(
            direction, current_price, atr, validation_count
        )
        
        # Create signal
        signal = Signal(
            stock_id=stock.id,
            symbol=stock.symbol,
            signal_type=signal_type,
            status=SignalStatus.PENDING,
            entry_price=current_price,
            stop_loss=levels["stop_loss"],
            take_profit_1=levels["tp1"],
            take_profit_2=levels["tp2"],
            take_profit_3=levels["tp3"],
            probability=probability,
            confidence=confidence,
            risk_reward_ratio=levels["risk_reward"],
            sfp_validated=sfp_validated,
            chooch_validated=chooch_validated,
            fvg_validated=fvg_validated,
            validation_status=SignalValidation.VALIDATED if validation_count == 3 
                else SignalValidation.SFP,
            atr_value=atr,
            atr_multiplier=2.0,
            indicators=json.dumps({
                "sfp": sfp_validated,
                "chooch": chooch_result,
                "fvg": fvg_result,
                "atr_percent": round(atr_percent, 2)
            })
        )
        
        self.db.add(signal)
        self.db.commit()
        self.db.refresh(signal)
        
        # Create alert
        self._create_signal_alert(signal, "generated")
        
        # Send WebPush notification
        self._send_webpush_notification(signal)
        
        return signal
    
    def _calculate_confidence(self, validation_count: int, 
                              atr_percent: float, direction: str) -> float:
        """Calculate confidence score based on validations and ATR."""
        # Base confidence from validations (0-60 points)
        base = validation_count * 20
        
        # ATR volatility adjustment (-10 to +10)
        atr_factor = min(atr_percent * 2, 10)
        
        # Stronger direction signal = more confidence
        direction_bonus = 30 if direction else 0
        
        return min(base + atr_factor + direction_bonus, 100)
    
    def _calculate_price_levels(self, direction: str, 
                                 current_price: float, atr: float,
                                 validation_count: int) -> dict:
        """Calculate price levels using ATR dynamic thresholds."""
        # Stop loss: 2 ATR for valid signals
        sl_distance = atr * 2.0
        
        # Take profits: 1R, 2R, 3R
        if direction == "bullish":
            stop_loss = current_price - sl_distance
            tp1 = current_price + sl_distance
            tp2 = current_price + (sl_distance * 2)
            tp3 = current_price + (sl_distance * 3)
        else:
            stop_loss = current_price + sl_distance
            tp1 = current_price - sl_distance
            tp2 = current_price - (sl_distance * 2)
            tp3 = current_price - (sl_distance * 3)
        
        risk_reward = sl_distance / sl_distance  # Always 1:1 for first TP
        
        return {
            "stop_loss": round(stop_loss, 4),
            "tp1": round(tp1, 4),
            "tp2": round(tp2, 4),
            "tp3": round(tp3, 4),
            "risk_reward": round(risk_reward, 2)
        }
    
    def _create_signal_alert(self, signal: Signal, alert_type: str) -> None:
        """Create alert notification for signal event."""
        messages = {
            "generated": f"New {signal.signal_type.value} signal for {signal.symbol} at ${signal.entry_price} "
                        f"(confidence: {signal.confidence:.0f}%, probability: {signal.probability:.2f})",
            "triggered": f"Signal {signal.id} triggered for {signal.symbol}",
            "expired": f"Signal {signal.id} expired for {signal.symbol}",
            "stopped_out": f"Stop loss hit for {signal.symbol} signal {signal.id}",
            "tp_hit": f"Take profit hit for {signal.symbol} signal {signal.id}"
        }
        
        alert = SignalAlert(
            signal_id=signal.id,
            alert_type=alert_type,
            message=messages.get(alert_type, f"Signal event: {alert_type}"),
            sent=False
        )
        
        self.db.add(alert)
        self.db.commit()
    
    def _send_webpush_notification(self, signal: Signal) -> None:
        """Send WebPush notification for new signal."""
        try:
            # Import here to avoid circular imports
            from apps.workers.push_dispatch.webpush_service import send_signal_notification
            from domains.auth.user import User
            
            # Get user for this signal's subscriptions
            user = self.db.query(User).filter(User.id == signal.stock.user_id).first()
            if not user:
                return
            
            # Build signal data for notification
            signal_data = {
                "signal_id": signal.id,
                "symbol": signal.symbol,
                "signal_type": signal.signal_type.value,
                "entry_price": float(signal.entry_price),
                "confidence": signal.confidence
            }
            
            # Send async notification (fire and forget for now)
            import asyncio
            asyncio.create_task(
                send_signal_notification(self.db, user.id, signal_data)
            )
        except Exception as e:
            # Log but don't fail signal creation
            import logging
            logging.getLogger(__name__).warning(f"WebPush notification failed: {e}")


class SignalService:
    """Service layer for signal management."""
    
    def __init__(self, db: Session):
        self.db = db
        self.generator = SignalGenerator(db)
        # Import clustering service lazily to avoid circular imports
        self._cluster_service = None
    
    @property
    def cluster_service(self):
        """Lazy-load clustering service."""
        if self._cluster_service is None:
            from domains.signals.signal_clustering import SignalClusterService
            self._cluster_service = SignalClusterService(self.db)
        return self._cluster_service
    
    def create_signal_from_ohlcv(
        self,
        stock: Stock,
        high: list,
        low: list,
        close: list,
        volume: list,
        strategy_id: Optional[int] = None
    ) -> Optional[Signal]:
        """Create signal from OHLCV data."""
        return self.generator.generate_signal(
            stock, high, low, close, volume, strategy_id
        )
    
    def get_active_signals(self, symbol: Optional[str] = None) -> list[Signal]:
        """Get all active signals, optionally filtered by symbol."""
        query = self.db.query(Signal).filter(
            Signal.status.in_([SignalStatus.PENDING, SignalStatus.ACTIVE])
        )
        
        if symbol:
            query = query.filter(Signal.symbol == symbol.upper())
        
        return query.order_by(Signal.generated_at.desc()).all()
    
    def get_signal_by_id(self, signal_id: int) -> Optional[Signal]:
        """Get signal by ID."""
        return self.db.query(Signal).filter(Signal.id == signal_id).first()
    
    def trigger_signal(self, signal_id: int) -> Optional[Signal]:
        """Mark signal as triggered."""
        signal = self.get_signal_by_id(signal_id)
        if signal:
            signal.status = SignalStatus.TRIGGERED
            signal.triggered_at = datetime.utcnow()
            self.db.commit()
            self._create_alert(signal, "triggered")
            self.db.refresh(signal)
        return signal
    
    def expire_signal(self, signal_id: int) -> Optional[Signal]:
        """Mark signal as expired."""
        signal = self.get_signal_by_id(signal_id)
        if signal:
            signal.status = SignalStatus.EXPIRED
            signal.expired_at = datetime.utcnow()
            self.db.commit()
            self._create_alert(signal, "expired")
            self.db.refresh(signal)
        return signal
    
    def cancel_signal(self, signal_id: int) -> Optional[Signal]:
        """Cancel a signal."""
        signal = self.get_signal_by_id(signal_id)
        if signal:
            signal.status = SignalStatus.CANCELLED
            self.db.commit()
            self.db.refresh(signal)
        return signal
    
    def get_signals_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        signal_type: Optional[SignalType] = None
    ) -> list[Signal]:
        """Get signals within date range."""
        query = self.db.query(Signal).filter(
            Signal.generated_at >= start_date,
            Signal.generated_at <= end_date
        )
        
        if signal_type:
            query = query.filter(Signal.signal_type == signal_type)
        
        return query.order_by(Signal.generated_at.desc()).all()
    
    def get_signal_stats(self) -> dict:
        """Get signal statistics."""
        total = self.db.query(Signal).count()
        active = self.db.query(Signal).filter(
            Signal.status == SignalStatus.ACTIVE
        ).count()
        triggered = self.db.query(Signal).filter(
            Signal.status == SignalStatus.TRIGGERED
        ).count()
        
        avg_confidence = self.db.query(Signal).filter(
            Signal.confidence > 0
        ).with_entities(
            func.avg(Signal.confidence)
        ).scalar() or 0
        
        return {
            "total_signals": total,
            "active_signals": active,
            "triggered_signals": triggered,
            "average_confidence": round(avg_confidence, 2)
        }
    
    def _create_alert(self, signal: Signal, alert_type: str) -> None:
        """Create alert for signal event."""
        messages = {
            "triggered": f"Signal {signal.id} ({signal.signal_type.value}) triggered for {signal.symbol}",
            "expired": f"Signal {signal.id} expired for {signal.symbol}"
        }
        
        alert = SignalAlert(
            signal_id=signal.id,
            alert_type=alert_type,
            message=messages.get(alert_type, f"Signal event: {alert_type}"),
            sent=False
        )
        
        self.db.add(alert)
        self.db.commit()
    
    def get_clustered_signals(self, symbol: Optional[str] = None) -> list:
        """
        Get clustered/deduplicated signals.
        
        Args:
            symbol: Optional filter by symbol
            
        Returns:
            List of best signals from each cluster
        """
        return self.cluster_service.get_consolidated_signals(symbol)
    
    def get_cluster_summary(self, symbol: Optional[str] = None) -> dict:
        """
        Get summary of signal clusters.
        
        Args:
            symbol: Optional filter by symbol
            
        Returns:
            Dict with cluster summary
        """
        return self.cluster_service.get_cluster_summary(symbol)


# Import func for aggregation
from sqlalchemy import func
