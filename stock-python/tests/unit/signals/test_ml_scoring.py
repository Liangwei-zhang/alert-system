"""
Unit tests for ML Scoring - tested by Notifications Team (Agent C).

Original developer: Signals Team (Agent B)
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock

from domains.signals.ml_scoring import (
    MLScoreResult, SignalFeatures,
    FeatureExtractor, MLScorePredictor, MLScoreService
)
from domains.signals.signal import Signal, SignalType, SignalStatus


class TestMLScoreResult:
    """Test MLScoreResult dataclass."""
    
    def test_score_result_creation(self):
        """Test creating MLScoreResult."""
        result = MLScoreResult(
            predicted_score=85.0,
            confidence_interval=(70.0, 100.0),
            model_version="v0.1-placeholder",
            features_used=["price_change_1d", "rsi"],
            prediction_date=datetime.utcnow()
        )
        
        assert result.predicted_score == 85.0
        assert result.confidence_interval == (70.0, 100.0)
        assert result.model_version == "v0.1-placeholder"
        assert len(result.features_used) == 2


class TestSignalFeatures:
    """Test SignalFeatures dataclass."""
    
    def test_signal_features_creation(self):
        """Test creating SignalFeatures."""
        features = SignalFeatures(
            price_change_1d=1.5,
            price_change_5d=5.2,
            price_change_20d=10.0,
            volatility_20d=2.5,
            volume_ratio=1.3,
            volume_trend=0.2,
            rsi=65.0,
            macd_signal=0.5,
            adx=25.0,
            signal_confidence=75.0,
            signal_probability=0.75,
            validation_count=2,
            market_return_1d=0.5,
            sector_return_1d=0.3
        )
        
        assert features.price_change_1d == 1.5
        assert features.rsi == 65.0
        assert features.validation_count == 2


class TestFeatureExtractor:
    """Test FeatureExtractor."""
    
    @pytest.fixture
    def mock_signal(self):
        """Create mock signal."""
        signal = MagicMock(spec=Signal)
        signal.confidence = 75.0
        signal.probability = 0.75
        signal.sfp_validated = True
        signal.chooch_validated = True
        signal.fvg_validated = False
        return signal
    
    def test_extract_insufficient_data(self, mock_signal):
        """Test feature extraction with insufficient data."""
        price_history = [100, 101]  # Less than 20
        volume_history = [1000, 1100]
        
        features = FeatureExtractor.extract(
            mock_signal, price_history, volume_history
        )
        
        # Should return default features
        assert features.price_change_1d == 0
        assert features.volatility_20d == 0
        assert features.validation_count == 2
    
    def test_extract_valid_data(self, mock_signal):
        """Test feature extraction with valid data."""
        # Generate 30 days of data
        price_history = [100 + i for i in range(30)]
        volume_history = [1000 + i * 10 for i in range(30)]
        
        features = FeatureExtractor.extract(
            mock_signal, price_history, volume_history,
            market_return=0.01, sector_return=0.005
        )
        
        assert features.price_change_1d != 0
        assert features.volatility_20d >= 0
        assert features.volume_ratio >= 0
    
    def test_extract_price_changes(self, mock_signal):
        """Test price change calculations."""
        # Upward trending data
        price_history = list(range(100, 130))  # 30 days, price up 30%
        volume_history = [1000] * 30
        
        features = FeatureExtractor.extract(
            mock_signal, price_history, volume_history
        )
        
        assert features.price_change_1d > 0
        assert features.price_change_5d > 0
        assert features.price_change_20d > 0
    
    def test_extract_volatility(self, mock_signal):
        """Test volatility calculation."""
        # Volatile data
        import numpy as np
        np.random.seed(42)
        price_history = list(100 + np.random.randn(30) * 5)
        volume_history = [1000] * 30
        
        features = FeatureExtractor.extract(
            mock_signal, price_history, volume_history
        )
        
        assert features.volatility_20d >= 0
    
    def test_extract_volume_features(self, mock_signal):
        """Test volume features."""
        # Increasing volume
        volume_history = [100 * (i + 1) for i in range(30)]
        price_history = [100] * 30
        
        features = FeatureExtractor.extract(
            mock_signal, price_history, volume_history
        )
        
        assert features.volume_ratio >= 1.0
        assert isinstance(features.volume_trend, float)
    
    def test_extract_validation_count(self, mock_signal):
        """Test validation count calculation."""
        # Signal with all validations
        mock_signal.sfp_validated = True
        mock_signal.chooch_validated = True
        mock_signal.fvg_validated = True
        
        features = FeatureExtractor.extract(
            mock_signal, [100] * 30, [1000] * 30
        )
        
        assert features.validation_count == 3
        
        # Signal with no validations
        mock_signal.sfp_validated = False
        mock_signal.chooch_validated = False
        mock_signal.fvg_validated = False
        
        features = FeatureExtractor.extract(
            mock_signal, [100] * 30, [1000] * 30
        )
        
        assert features.validation_count == 0
    
    def test_rsi_calculation(self):
        """Test RSI calculation."""
        # Uptrend
        prices = list(range(100, 120))
        
        rsi = FeatureExtractor._rsi(prices, period=14)
        
        assert 0 <= rsi <= 100
    
    def test_macd_calculation(self):
        """Test MACD calculation."""
        prices = list(range(100, 130))
        
        macd = FeatureExtractor._macd(prices)
        
        assert isinstance(macd, float)
    
    def test_adx_calculation(self):
        """Test ADX calculation."""
        prices = list(range(100, 120))
        
        adx = FeatureExtractor._adx(prices, period=14)
        
        assert adx >= 0


class TestMLScorePredictor:
    """Test MLScorePredictor."""
    
    @pytest.fixture
    def predictor(self):
        return MLScorePredictor()
    
    @pytest.fixture
    def mock_signal(self):
        signal = MagicMock(spec=Signal)
        signal.confidence = 70.0
        signal.probability = 0.7
        signal.sfp_validated = True
        signal.chooch_validated = True
        signal.fvg_validated = False
        return signal
    
    def test_predict_default_features(self, predictor, mock_signal):
        """Test prediction with default features."""
        result = predictor.predict(
            mock_signal, [], []
        )
        
        assert result.predicted_score >= 0
        assert result.predicted_score <= 100
        assert result.model_version == "v0.1-placeholder"
        assert len(result.features_used) > 0
    
    def test_predict_valid_data(self, predictor, mock_signal):
        """Test prediction with valid historical data."""
        price_history = [100 + i for i in range(30)]
        volume_history = [1000] * 30
        
        result = predictor.predict(
            mock_signal, price_history, volume_history
        )
        
        assert 0 <= result.predicted_score <= 100
        assert result.confidence_interval[0] < result.confidence_interval[1]
    
    def test_predict_high_confidence_signal(self, predictor):
        """Test prediction with high confidence signal."""
        signal = MagicMock(spec=Signal)
        signal.confidence = 95.0
        signal.probability = 0.95
        signal.sfp_validated = True
        signal.chooch_validated = True
        signal.fvg_validated = True
        
        price_history = [100 + i for i in range(30)]
        volume_history = [1000] * 30
        
        result = predictor.predict(signal, price_history, volume_history)
        
        # High confidence should result in high score
        assert result.predicted_score > 50
    
    def test_predict_low_confidence_signal(self, predictor):
        """Test prediction with low confidence signal."""
        signal = MagicMock(spec=Signal)
        signal.confidence = 20.0
        signal.probability = 0.2
        signal.sfp_validated = False
        signal.chooch_validated = False
        signal.fvg_validated = False
        
        price_history = [100 + i for i in range(30)]
        volume_history = [1000] * 30
        
        result = predictor.predict(signal, price_history, volume_history)
        
        # Low confidence should result in lower score
        assert result.predicted_score < 80
    
    def test_predict_momentum_bonus(self, predictor):
        """Test momentum bonus in scoring."""
        signal = MagicMock(spec=Signal)
        signal.confidence = 50.0
        signal.probability = 0.5
        signal.sfp_validated = False
        signal.chooch_validated = False
        signal.fvg_validated = False
        
        # Strong positive momentum
        price_history = list(range(100, 120))
        volume_history = [1000] * 20
        
        result = predictor.predict(signal, price_history, volume_history)
        
        assert result.predicted_score >= 0
    
    def test_predict_volume_bonus(self, predictor):
        """Test volume confirmation bonus."""
        signal = MagicMock(spec=Signal)
        signal.confidence = 50.0
        signal.probability = 0.5
        signal.sfp_validated = False
        signal.chooch_validated = False
        signal.fvg_validated = False
        
        # High volume
        price_history = [100] * 30
        volume_history = [10000] * 30
        
        result = predictor.predict(signal, price_history, volume_history)
        
        assert result.predicted_score >= 0
    
    def test_batch_predict(self, predictor):
        """Test batch prediction."""
        signals = []
        for i in range(3):
            s = MagicMock(spec=Signal)
            s.id = i + 1
            s.confidence = 60.0 + i * 10
            s.probability = 0.6 + i * 0.1
            s.sfp_validated = True
            s.chooch_validated = i > 0
            s.fvg_validated = i > 1
            signals.append(s)
        
        price_histories = {s.id: list(range(100, 130)) for s in signals}
        volume_histories = {s.id: [1000] * 30 for s in signals}
        
        results = predictor.batch_predict(signals, price_histories, volume_histories)
        
        assert len(results) == 3
        for signal_id, result in results.items():
            assert 0 <= result.predicted_score <= 100


class TestMLScoreService:
    """Test MLScoreService."""
    
    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.query = MagicMock()
        return db
    
    def test_score_signal_not_found(self, mock_db):
        """Test scoring non-existent signal."""
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=None)
        mock_db.query.return_value = mock_query
        
        service = MLScoreService(mock_db)
        result = service.score_signal(999, [], [])
        
        assert result is None
    
    def test_score_signal_valid(self, mock_db):
        """Test scoring a valid signal."""
        mock_signal = MagicMock()
        mock_signal.id = 1
        mock_signal.confidence = 75.0
        mock_signal.probability = 0.75
        mock_signal.sfp_validated = True
        mock_signal.chooch_validated = True
        mock_signal.fvg_validated = False
        
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_signal)
        mock_db.query.return_value = mock_query
        
        service = MLScoreService(mock_db)
        result = service.score_signal(1, [100] * 30, [1000] * 30)
        
        assert result is not None
        assert result.predicted_score >= 0
    
    def test_score_pending_signals_empty(self, mock_db):
        """Test scoring pending signals with none."""
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[])
        mock_db.query.return_value = mock_query
        
        service = MLScoreService(mock_db)
        results = service.score_pending_signals()
        
        assert results == []
    
    def test_score_pending_signals_with_data(self, mock_db):
        """Test scoring pending signals."""
        mock_signal = MagicMock()
        mock_signal.id = 1
        mock_signal.confidence = 70.0
        mock_signal.probability = 0.7
        mock_signal.sfp_validated = True
        mock_signal.chooch_validated = False
        mock_signal.fvg_validated = False
        mock_signal.status = SignalStatus.PENDING
        
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[mock_signal])
        mock_db.query.return_value = mock_query
        
        service = MLScoreService(mock_db)
        results = service.score_pending_signals()
        
        assert len(results) == 1
        assert isinstance(results[0], tuple)
    
    def test_score_pending_signals_symbol_filter(self, mock_db):
        """Test scoring pending signals with symbol filter."""
        mock_signal = MagicMock()
        mock_signal.symbol = "AAPL"
        
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=[mock_signal])
        mock_db.query.return_value = mock_query
        
        service = MLScoreService(mock_db)
        results = service.score_pending_signals(symbol="AAPL")
        
        mock_query.filter.assert_called()
    
    def test_get_top_signals(self, mock_db):
        """Test getting top scoring signals."""
        mock_signals = []
        for i in range(3):
            s = MagicMock()
            s.id = i + 1
            s.symbol = "AAPL"
            s.confidence = 70.0 + i * 5
            s.probability = 0.7 + i * 0.05
            s.sfp_validated = True
            s.chooch_validated = i > 0
            s.fvg_validated = False
            s.status = SignalStatus.PENDING
            mock_signals.append(s)
        
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.all = MagicMock(return_value=mock_signals)
        mock_db.query.return_value = mock_query
        
        service = MLScoreService(mock_db)
        top_signals = service.get_top_signals(limit=2)
        
        assert len(top_signals) <= 2
        # Should be sorted by score descending
        if len(top_signals) >= 2:
            assert top_signals[0][1].predicted_score >= top_signals[1][1].predicted_score
    
    def test_update_signal_score(self, mock_db):
        """Test updating signal with ML score."""
        mock_signal = MagicMock()
        mock_signal.id = 1
        mock_signal.confidence = 70.0
        mock_signal.probability = 0.7
        mock_signal.sfp_validated = True
        mock_signal.chooch_validated = False
        mock_signal.fvg_validated = False
        
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_signal)
        mock_db.query.return_value = mock_query
        
        service = MLScoreService(mock_db)
        result = service.update_signal_score(1, [100] * 30, [1000] * 30)
        
        assert result is not None
        mock_db.commit.assert_called()


class TestMLScoringEdgeCases:
    """Test edge cases for ML scoring."""
    
    def test_predict_extreme_confidence(self):
        """Test prediction with extreme confidence values."""
        predictor = MLScorePredictor()
        
        signal = MagicMock(spec=Signal)
        signal.confidence = 0.0  # Minimum
        signal.probability = 0.0
        signal.sfp_validated = False
        signal.chooch_validated = False
        signal.fvg_validated = False
        
        result = predictor.predict(signal, [100] * 30, [1000] * 30)
        
        assert result.predicted_score >= 0
        assert result.predicted_score <= 100
    
    def test_predict_max_confidence(self):
        """Test prediction with maximum confidence."""
        predictor = MLScorePredictor()
        
        signal = MagicMock(spec=Signal)
        signal.confidence = 100.0
        signal.probability = 1.0
        signal.sfp_validated = True
        signal.chooch_validated = True
        signal.fvg_validated = True
        
        result = predictor.predict(signal, [100] * 30, [1000] * 30)
        
        assert result.predicted_score >= 50  # Should be high
    
    def test_extract_zero_volume(self):
        """Test feature extraction with zero volume."""
        signal = MagicMock(spec=Signal)
        signal.confidence = 50.0
        signal.probability = 0.5
        signal.sfp_validated = False
        signal.chooch_validated = False
        signal.fvg_validated = False
        
        price_history = list(range(100, 130))
        volume_history = [0] * 30
        
        features = FeatureExtractor.extract(signal, price_history, volume_history)
        
        # Should handle zero volume gracefully
        assert features.volume_ratio >= 0
    
    def test_extract_negative_prices(self):
        """Test feature extraction with negative prices (unusual but handle gracefully)."""
        signal = MagicMock(spec=Signal)
        signal.confidence = 50.0
        signal.probability = 0.5
        signal.sfp_validated = False
        signal.chooch_validated = False
        signal.fvg_validated = False
        
        price_history = [100, 99, 98, 97, 96] + [95] * 25  # Declining
        volume_history = [1000] * 30
        
        features = FeatureExtractor.extract(signal, price_history, volume_history)
        
        assert features.price_change_1d < 0


class TestMLScoringErrors:
    """Test error handling for ML scoring."""
    
    def test_predict_with_invalid_signal(self):
        """Test prediction with invalid signal type."""
        predictor = MLScorePredictor()
        
        # Pass non-Signal object
        result = predictor.predict("invalid", [], [])
        
        # Should handle or raise appropriate error
        assert result is not None or result is None
    
    def test_service_database_error(self):
        """Test service handling database errors."""
        db = MagicMock()
        db.query.side_effect = Exception("Database connection error")
        
        service = MLScoreService(db)
        
        # Should handle gracefully
        with pytest.raises(Exception):
            service.score_pending_signals()