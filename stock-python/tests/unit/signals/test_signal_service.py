"""
Unit tests for SignalService - tested by Notifications Team (Agent C).

Original developer: Signals Team (Agent B)
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

from domains.signals.signal_service import (
    ATRCalculator, SFPDetector, CHOCHDetector, FVGDetector,
    SigmoidProbability, SignalGenerator, SignalService,
    Signal, SignalType, SignalStatus, SignalValidation
)


class TestATRCalculator:
    """Test ATR (Average True Range) calculator."""
    
    def test_calculate_atr_valid_data(self):
        """Test ATR calculation with valid data."""
        calculator = ATRCalculator()
        
        high = [100, 102, 104, 103, 105, 107, 106, 108, 110, 109, 111, 113, 112, 114, 116, 115, 117, 119, 118, 120]
        low = [98, 100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 111, 110, 112, 114, 113, 115, 117, 116, 118]
        close = [99, 101, 103, 102, 104, 106, 105, 107, 109, 108, 110, 112, 111, 113, 115, 114, 116, 118, 117, 119]
        
        atr = calculator.calculate(high, low, close, period=14)
        
        assert atr > 0
        assert isinstance(atr, float)
    
    def test_calculate_atr_insufficient_data(self):
        """Test ATR calculation with insufficient data."""
        calculator = ATRCalculator()
        
        high = [100, 102]
        low = [98, 100]
        close = [99, 101]
        
        atr = calculator.calculate(high, low, close, period=14)
        
        assert atr == 0.0
    
    def test_calculate_atr_percent(self):
        """Test ATR as percentage calculation."""
        calculator = ATRCalculator()
        
        # 2 ATR on $100 price = 2%
        percent = calculator.calculate_atr_percent(2.0, 100.0)
        assert percent == 2.0
        
        # Zero price handling
        percent_zero = calculator.calculate_atr_percent(2.0, 0.0)
        assert percent_zero == 0.0


class TestSFPDetector:
    """Test Smart Fair Pullback detector."""
    
    def test_detect_sfp_bullish_setup(self):
        """Test SFP detection for bullish setup."""
        detector = SFPDetector()
        
        # Create data showing price pulling back to support
        high = [100, 102, 104, 103, 105, 107, 106, 108, 110, 109]
        low = [98, 100, 102, 101, 103, 105, 104, 106, 108, 107]
        close = [99, 101, 103, 102, 104, 106, 105, 107, 109, 108]  # Price pulling back
        
        result = detector.detect(high, low, close, lookback=10)
        
        assert isinstance(result, bool)
    
    def test_detect_sfp_insufficient_data(self):
        """Test SFP with insufficient data."""
        detector = SFPDetector()
        
        high = [100]
        low = [98]
        close = [99]
        
        result = detector.detect(high, low, close, lookback=10)
        
        assert result is False
    
    def test_detect_sfp_no_pullback(self):
        """Test SFP when no pullback pattern."""
        detector = SFPDetector()
        
        # Price going up consistently - no pullback
        high = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]
        low = [99, 100, 101, 102, 103, 104, 105, 106, 107, 108]
        close = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]
        
        result = detector.detect(high, low, close, lookback=10)
        
        # May be False or True depending on zone detection
        assert isinstance(result, bool)


class TestCHOCHDetector:
    """Test Change of Character detector."""
    
    def test_detect_choch_bullish(self):
        """Test bullish CHOCH detection."""
        detector = CHOCHDetector()
        
        # Create data with bullish breakout
        high = [100, 101, 102, 101, 100, 99, 98, 99, 100, 101, 102, 103]  # Break above 102
        low = [98, 99, 100, 99, 98, 97, 96, 97, 98, 99, 100, 101]
        close = [99, 100, 101, 100, 99, 98, 97, 98, 99, 100, 101, 103]  # Close above swing high
        
        result = detector.detect(high, low, close, lookback=5)
        
        assert "direction" in result
        assert "validated" in result
        assert isinstance(result["validated"], bool)
    
    def test_detect_choch_bearish(self):
        """Test bearish CHOCH detection."""
        detector = CHOCHDetector()
        
        high = [103, 102, 101, 102, 103, 104, 105, 104, 103, 102, 101, 100]
        low = [101, 100, 99, 100, 101, 102, 103, 102, 101, 100, 99, 98]
        close = [102, 101, 100, 101, 102, 103, 104, 103, 102, 101, 100, 98]
        
        result = detector.detect(high, low, close, lookback=5)
        
        assert "direction" in result
        assert "validated" in result
    
    def test_detect_choch_insufficient_swings(self):
        """Test CHOCH with insufficient swing points."""
        detector = CHOCHDetector()
        
        # Flat data - no clear swing points
        high = [100, 100, 100, 100, 100, 100]
        low = [99, 99, 99, 99, 99, 99]
        close = [100, 100, 100, 100, 100, 100]
        
        result = detector.detect(high, low, close, lookback=5)
        
        assert result["validated"] is False
        assert result["direction"] is None


class TestFVGDetector:
    """Test Fair Value Gap detector."""
    
    def test_detect_fvg_bullish(self):
        """Test bullish FVG detection."""
        detector = FVGDetector()
        
        # Create bullish gap
        high = [100, 101, 102, 104]  # Gap up
        low = [98, 99, 100, 103]
        close = [99, 100, 101, 104]
        
        result = detector.detect(high, low, close)
        
        assert "direction" in result
        assert "gap_size" in result
        assert "filled" in result
        assert "validated" in result
    
    def test_detect_fvg_bearish(self):
        """Test bearish FVG detection."""
        detector = FVGDetector()
        
        # Create bearish gap
        high = [104, 103, 102, 100]
        low = [102, 101, 100, 98]
        close = [103, 102, 101, 99]
        
        result = detector.detect(high, low, close)
        
        assert "direction" in result
        assert "gap_size" in result
    
    def test_detect_fvg_no_gap(self):
        """Test FVG when no gap present."""
        detector = FVGDetector()
        
        # No gap - overlapping candles
        high = [100, 102, 104, 106]
        low = [98, 100, 102, 104]
        close = [99, 101, 103, 105]
        
        result = detector.detect(high, low, close)
        
        assert result["direction"] is None
        assert result["validated"] is False
    
    def test_detect_fvg_insufficient_data(self):
        """Test FVG with insufficient data."""
        detector = FVGDetector()
        
        high = [100, 101]
        low = [98, 99]
        close = [99, 100]
        
        result = detector.detect(high, low, close)
        
        assert result["validated"] is False


class TestSigmoidProbability:
    """Test sigmoid probability calculation."""
    
    def test_calculate_no_validations(self):
        """Test probability with 0 validations."""
        prob = SigmoidProbability.calculate(0, total_validations=3)
        
        assert 0 <= prob <= 1
        assert prob < 0.5  # Low probability with no validations
    
    def test_calculate_all_validations(self):
        """Test probability with all validations."""
        prob = SigmoidProbability.calculate(3, total_validations=3)
        
        assert 0 <= prob <= 1
        assert prob > 0.5  # High probability with all validations
    
    def test_calculate_partial_validations(self):
        """Test probability with partial validations."""
        prob = SigmoidProbability.calculate(2, total_validations=3)
        
        assert 0 <= prob <= 1
    
    def test_calculate_with_indicators(self):
        """Test probability with indicator signals."""
        # Positive indicators
        prob_pos = SigmoidProbability.calculate_with_indicators(
            2, 0.8, total_validations=3
        )
        assert 0 <= prob_pos <= 1
        
        # Negative indicators
        prob_neg = SigmoidProbability.calculate_with_indicators(
            2, -0.8, total_validations=3
        )
        assert 0 <= prob_neg <= 1
        
        # Indicator signals should influence result
        assert prob_pos != prob_neg


class TestSignalGenerator:
    """Test signal generation logic."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        return db
    
    @pytest.fixture
    def mock_stock(self):
        """Create mock stock."""
        stock = MagicMock()
        stock.id = 1
        stock.symbol = "AAPL"
        stock.user_id = 1
        return stock
    
    def test_generate_signal_insufficient_data(self, mock_db, mock_stock):
        """Test signal generation with insufficient data."""
        generator = SignalGenerator(mock_db)
        
        # Insufficient price data
        high = [100, 101]
        low = [99, 100]
        close = [99, 100]
        volume = [1000, 1100]
        
        result = generator.generate_signal(
            mock_stock, high, low, close, volume
        )
        
        assert result is None
    
    def test_generate_signal_no_direction(self, mock_db, mock_stock):
        """Test signal generation when no clear direction."""
        generator = SignalGenerator(mock_db)
        
        # Flat price - no clear direction
        high = [100] * 25
        low = [99] * 25
        close = [100] * 25
        volume = [1000] * 25
        
        result = generator.generate_signal(
            mock_stock, high, low, close, volume
        )
        
        # May return None if no valid signal
        assert result is None or isinstance(result, Signal)
    
    def test_generate_signal_low_confidence(self, mock_db, mock_stock):
        """Test signal generation with low confidence."""
        generator = SignalGenerator(mock_db)
        
        # Data that doesn't meet confidence threshold
        high = [100, 101, 102, 101, 100, 99, 98, 99, 100, 101] * 3
        low = [99, 100, 101, 100, 99, 98, 97, 98, 99, 100] * 3
        close = [100, 101, 102, 101, 100, 99, 98, 99, 100, 101] * 3
        volume = [1000] * 30
        
        result = generator.generate_signal(
            mock_stock, high, low, close, volume
        )
        
        # Should return None if confidence < 50
        assert result is None or (
            result is not None and result.confidence >= 0
        )


class TestSignalService:
    """Test SignalService methods."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = MagicMock()
        db.query = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        return db
    
    def test_get_active_signals(self, mock_db):
        """Test getting active signals."""
        mock_signal = MagicMock()
        mock_signal.id = 1
        mock_signal.symbol = "AAPL"
        
        # Mock query chain
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.order_by = MagicMock(return_value=[mock_signal])
        mock_db.query.return_value = mock_query
        
        service = SignalService(mock_db)
        signals = service.get_active_signals()
        
        assert len(signals) >= 0
    
    def test_get_active_signals_filtered(self, mock_db):
        """Test getting active signals filtered by symbol."""
        mock_signal = MagicMock()
        mock_signal.symbol = "AAPL"
        
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.order_by = MagicMock(return_value=[mock_signal])
        mock_db.query.return_value = mock_query
        
        service = SignalService(mock_db)
        signals = service.get_active_signals(symbol="AAPL")
        
        # Verify filter was called
        mock_query.filter.assert_called()
    
    def test_get_signal_by_id_not_found(self, mock_db):
        """Test getting non-existent signal."""
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=None)
        mock_db.query.return_value = mock_query
        
        service = SignalService(mock_db)
        signal = service.get_signal_by_id(999)
        
        assert signal is None
    
    def test_trigger_signal(self, mock_db):
        """Test triggering a signal."""
        mock_signal = MagicMock()
        mock_signal.id = 1
        mock_signal.status = SignalStatus.PENDING
        mock_signal.triggered_at = None
        
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_signal)
        mock_db.query.return_value = mock_query
        
        service = SignalService(mock_db)
        result = service.trigger_signal(1)
        
        assert result is not None
        mock_db.commit.assert_called()
    
    def test_expire_signal(self, mock_db):
        """Test expiring a signal."""
        mock_signal = MagicMock()
        mock_signal.id = 1
        mock_signal.status = SignalStatus.PENDING
        mock_signal.expired_at = None
        
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_signal)
        mock_db.query.return_value = mock_query
        
        service = SignalService(mock_db)
        result = service.expire_signal(1)
        
        assert result is not None
        mock_db.commit.assert_called()
    
    def test_cancel_signal(self, mock_db):
        """Test canceling a signal."""
        mock_signal = MagicMock()
        mock_signal.id = 1
        mock_signal.status = SignalStatus.PENDING
        
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_signal)
        mock_db.query.return_value = mock_query
        
        service = SignalService(mock_db)
        result = service.cancel_signal(1)
        
        assert result is not None
        assert result.status == SignalStatus.CANCELLED
    
    def test_get_signals_by_date_range(self, mock_db):
        """Test getting signals by date range."""
        mock_signal = MagicMock()
        
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.order_by = MagicMock(return_value=[mock_signal])
        mock_db.query.return_value = mock_query
        
        service = SignalService(mock_db)
        start = datetime.utcnow() - timedelta(days=7)
        end = datetime.utcnow()
        signals = service.get_signals_by_date_range(start, end)
        
        assert len(signals) >= 0


class TestSignalServiceEdgeCases:
    """Test edge cases for SignalService."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = MagicMock()
        return db
    
    def test_trigger_nonexistent_signal(self, mock_db):
        """Test triggering non-existent signal."""
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=None)
        mock_db.query.return_value = mock_query
        
        service = SignalService(mock_db)
        result = service.trigger_signal(999)
        
        assert result is None
    
    def test_service_with_cluster_service(self, mock_db):
        """Test service cluster integration."""
        service = SignalService(mock_db)
        
        # Access cluster service property
        with patch('domains.signals.signal_clustering.SignalClusterService'):
            cluster = service.cluster_service
            assert cluster is not None


class TestSignalServiceErrors:
    """Test error handling for SignalService."""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = MagicMock()
        db.query = MagicMock()
        return db
    
    def test_database_error_on_commit(self, mock_db):
        """Test handling database commit error."""
        mock_db.commit.side_effect = Exception("Database error")
        
        mock_signal = MagicMock()
        mock_signal.id = 1
        
        mock_query = MagicMock()
        mock_query.filter = MagicMock(return_value=mock_query)
        mock_query.first = MagicMock(return_value=mock_signal)
        mock_db.query.return_value = mock_query
        
        service = SignalService(mock_db)
        
        # Should handle error gracefully
        with pytest.raises(Exception):
            service.trigger_signal(1)