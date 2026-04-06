"""
ML-based signal scoring (placeholder for future ML models).

Features:
- ML model interface
- Feature extraction for ML models
- Score prediction placeholder
- Historical performance tracking

Note: This is a placeholder for future ML-based signal scoring.
Actual ML model integration will be added when:
- Training data is sufficient
- Feature engineering is finalized
- Model governance is established
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from domains.signals.signal import Signal, SignalStatus


@dataclass
class MLScoreResult:
    """ML-based score result."""
    predicted_score: float
    confidence_interval: tuple[float, float]
    model_version: str
    features_used: list[str]
    prediction_date: datetime


@dataclass
class SignalFeatures:
    """Extracted features for ML model."""
    # Price features
    price_change_1d: float
    price_change_5d: float
    price_change_20d: float
    volatility_20d: float
    
    # Volume features
    volume_ratio: float
    volume_trend: float
    
    # Technical features
    rsi: float
    macd_signal: float
    adx: float
    
    # Signal features
    signal_confidence: float
    signal_probability: float
    validation_count: int
    
    # Market features
    market_return_1d: float
    sector_return_1d: float


class FeatureExtractor:
    """Extract features for ML model input."""
    
    @staticmethod
    def extract(
        signal: Signal,
        price_history: list[float],
        volume_history: list[float],
        market_return: float = 0,
        sector_return: float = 0
    ) -> SignalFeatures:
        """
        Extract features from signal and historical data.
        
        Args:
            signal: Signal to extract features from
            price_history: Historical close prices
            volume_history: Historical volumes
            market_return: Market return for same period
            sector_return: Sector return for same period
            
        Returns:
            SignalFeatures object
        """
        if not price_history or len(price_history) < 20:
            # Return default features if insufficient data
            return SignalFeatures(
                price_change_1d=0,
                price_change_5d=0,
                price_change_20d=0,
                volatility_20d=0,
                volume_ratio=1.0,
                volume_trend=0,
                rsi=50,
                macd_signal=0,
                adx=0,
                signal_confidence=signal.confidence,
                signal_probability=signal.probability,
                validation_count=sum([
                    signal.sfp_validated,
                    signal.chooch_validated,
                    signal.fvg_validated
                ]),
                market_return_1d=market_return,
                sector_return_1d=sector_return
            )
        
        # Calculate price changes
        current_price = price_history[-1]
        
        change_1d = (price_history[-1] - price_history[-2]) / price_history[-2] if len(price_history) >= 2 else 0
        change_5d = (price_history[-1] - price_history[-5]) / price_history[-5] if len(price_history) >= 5 else 0
        change_20d = (price_history[-1] - price_history[-20]) / price_history[-20] if len(price_history) >= 20 else 0
        
        # Calculate volatility
        returns = np.diff(price_history[-20:]) / price_history[-20:-1]
        volatility = np.std(returns) * 100 if len(returns) > 1 else 0
        
        # Volume features
        avg_volume = np.mean(volume_history[-20:]) if volume_history else 1
        recent_volume = volume_history[-1] if volume_history else 1
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
        
        volume_trend = 0
        if len(volume_history) >= 10:
            first_half = np.mean(volume_history[-10:-5])
            second_half = np.mean(volume_history[-5:])
            volume_trend = (second_half / first_half - 1) if first_half > 0 else 0
        
        # Technical indicators (simplified)
        rsi = FeatureExtractor._rsi(price_history)
        macd = FeatureExtractor._macd(price_history)
        adx = FeatureExtractor._adx(price_history)
        
        # Validation count
        validation_count = sum([
            signal.sfp_validated,
            signal.chooch_validated,
            signal.fvg_validated
        ])
        
        return SignalFeatures(
            price_change_1d=round(change_1d * 100, 2),
            price_change_5d=round(change_5d * 100, 2),
            price_change_20d=round(change_20d * 100, 2),
            volatility_20d=round(volatility, 2),
            volume_ratio=round(volume_ratio, 2),
            volume_trend=round(volume_trend, 2),
            rsi=round(rsi, 1),
            macd_signal=round(macd, 4),
            adx=round(adx, 1),
            signal_confidence=signal.confidence,
            signal_probability=signal.probability,
            validation_count=validation_count,
            market_return_1d=round(market_return * 100, 2),
            sector_return_1d=round(sector_return * 100, 2)
        )
    
    @staticmethod
    def _rsi(prices: list, period: int = 14) -> float:
        """Calculate RSI."""
        if len(prices) < period + 1:
            return 50
        
        deltas = np.diff(prices[-period-1:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def _macd(prices: list) -> float:
        """Calculate MACD."""
        if len(prices) < 26:
            return 0
        
        # Simplified MACD
        ema_12 = np.mean(prices[-12:])
        ema_26 = np.mean(prices[-26:])
        
        return ema_12 - ema_26
    
    @staticmethod
    def _adx(prices: list, period: int = 14) -> float:
        """Calculate simplified ADX."""
        if len(prices) < period + 1:
            return 0
        
        # Very simplified - just use price range
        recent = prices[-period:]
        return (max(recent) - min(recent)) / np.mean(recent) * 100


class MLScorePredictor:
    """ML-based score prediction (placeholder)."""
    
    def __init__(self, model_version: str = "v0.1-placeholder"):
        self.model_version = model_version
        self.feature_extractor = FeatureExtractor()
    
    def predict(
        self,
        signal: Signal,
        price_history: list[float],
        volume_history: list[float],
        market_return: float = 0,
        sector_return: float = 0
    ) -> MLScoreResult:
        """
        Predict ML-based score for signal.
        
        Currently returns a weighted combination of existing
        signal attributes as placeholder.
        
        Args:
            signal: Signal to score
            price_history: Historical prices
            volume_history: Historical volumes
            market_return: Market return
            sector_return: Sector return
            
        Returns:
            MLScoreResult with predicted score
        """
        # Extract features
        features = self.feature_extractor.extract(
            signal, price_history, volume_history,
            market_return, sector_return
        )
        
        # Placeholder scoring logic:
        # This will be replaced with actual ML model
        
        # Base score from signal confidence
        base_score = features.signal_confidence
        
        # Adjustment factors
        validation_bonus = features.validation_count * 5  # +5 per validation
        
        # Momentum bonus/penalty
        momentum_bonus = 0
        if features.price_change_5d > 5:
            momentum_bonus += 5
        elif features.price_change_5d < -5:
            momentum_bonus -= 5
        
        # Volume confirmation bonus
        volume_bonus = 0
        if features.volume_ratio > 1.5:
            volume_bonus += 5
        elif features.volume_ratio < 0.5:
            volume_bonus -= 5
        
        # RSI adjustment
        rsi_bonus = 0
        if features.rsi < 30:  # Oversold - potential bounce
            rsi_bonus += 5
        elif features.rsi > 70:  # Overbought
            rsi_bonus -= 5
        
        # Calculate final score
        predicted_score = (
            base_score +
            validation_bonus +
            momentum_bonus +
            volume_bonus +
            rsi_bonus
        )
        
        # Normalize to 0-100
        predicted_score = max(0, min(100, predicted_score))
        
        # Confidence interval (wide for placeholder)
        confidence_interval = (
            predicted_score - 15,
            predicted_score + 15
        )
        
        return MLScoreResult(
            predicted_score=round(predicted_score, 1),
            confidence_interval=(
                max(0, round(confidence_interval[0], 1)),
                min(100, round(confidence_interval[1], 1))
            ),
            model_version=self.model_version,
            features_used=[
                "price_change_1d", "price_change_5d", "price_change_20d",
                "volatility_20d", "volume_ratio", "volume_trend",
                "rsi", "signal_confidence", "validation_count"
            ],
            prediction_date=datetime.utcnow()
        )
    
    def batch_predict(
        self,
        signals: list[Signal],
        price_histories: dict[int, list[float]],
        volume_histories: dict[int, list[float]]
    ) -> dict[int, MLScoreResult]:
        """
        Predict scores for multiple signals.
        
        Args:
            signals: List of signals
            price_histories: Dict mapping signal_id to price history
            volume_histories: Dict mapping signal_id to volume history
            
        Returns:
            Dict mapping signal_id to MLScoreResult
        """
        results = {}
        
        for signal in signals:
            price_history = price_histories.get(signal.id, [])
            volume_history = volume_histories.get(signal.id, [])
            
            results[signal.id] = self.predict(
                signal, price_history, volume_history
            )
        
        return results


class MLScoreService:
    """Service for ML-based signal scoring."""
    
    def __init__(self, db: Session):
        self.db = db
        self.predictor = MLScorePredictor()
    
    def score_signal(
        self,
        signal_id: int,
        price_history: list[float],
        volume_history: list[float],
        market_return: float = 0,
        sector_return: float = 0
    ) -> Optional[MLScoreResult]:
        """
        Score a signal using ML model.
        
        Args:
            signal_id: Signal ID
            price_history: Historical prices
            volume_history: Historical volumes
            market_return: Market return
            sector_return: Sector return
            
        Returns:
            MLScoreResult or None if signal not found
        """
        signal = self.db.query(Signal).filter(Signal.id == signal_id).first()
        
        if not signal:
            return None
        
        return self.predictor.predict(
            signal, price_history, volume_history,
            market_return, sector_return
        )
    
    def score_pending_signals(
        self,
        symbol: Optional[str] = None
    ) -> list[tuple[Signal, MLScoreResult]]:
        """
        Score all pending signals.
        
        Args:
            symbol: Optional filter by symbol
            
        Returns:
            List of (signal, MLScoreResult) tuples
        """
        query = self.db.query(Signal).filter(
            Signal.status.in_([SignalStatus.PENDING, SignalStatus.ACTIVE])
        )
        
        if symbol:
            query = query.filter(Signal.symbol == symbol.upper())
        
        signals = query.all()
        
        results = []
        for signal in signals:
            score_result = self.predictor.predict(signal, [], [])
            results.append((signal, score_result))
        
        return results
    
    def get_top_signals(
        self,
        limit: int = 10,
        symbol: Optional[str] = None
    ) -> list[tuple[Signal, MLScoreResult]]:
        """
        Get top scoring signals.
        
        Args:
            limit: Maximum number of signals
            symbol: Optional filter by symbol
            
        Returns:
            List of top (signal, MLScoreResult) tuples
        """
        scored_signals = self.score_pending_signals(symbol)
        
        # Sort by predicted score
        scored_signals.sort(
            key=lambda x: x[1].predicted_score,
            reverse=True
        )
        
        return scored_signals[:limit]
    
    def update_signal_score(
        self,
        signal_id: int,
        price_history: list[float],
        volume_history: list[float]
    ) -> Optional[Signal]:
        """
        Update signal with ML score.
        
        Args:
            signal_id: Signal ID
            price_history: Historical prices
            volume_history: Historical volumes
            
        Returns:
            Updated signal or None
        """
        score_result = self.score_signal(
            signal_id, price_history, volume_history
        )
        
        if not score_result:
            return None
        
        signal = self.db.query(Signal).filter(Signal.id == signal_id).first()
        
        # Update signal with ML score
        # Note: This adds new fields to Signal model if needed
        signal.confidence = max(signal.confidence, score_result.predicted_score)
        
        self.db.commit()
        self.db.refresh(signal)
        
        return signal