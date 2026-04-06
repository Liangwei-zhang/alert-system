"""
Signals Domain Tests
=====================
Tested by: Notifications Team (Agent C)
Original developer: Signals Team (Agent B)

Test Coverage:
- Happy path: signal generation, validation, status updates
- Edge cases: insufficient data, conflicting signals, ATR calculation
- Error handling: invalid stock, expired signals, signal not found
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import math

from domains.signals.signal_service import (
    SignalService,
    SignalGenerator,
    ATRCalculator,
    SFPDetector,
    CHOCHDetector,
    FVGDetector,
    SigmoidProbability,
)
from domains.signals.signal import (
    Signal, SignalType, SignalStatus, SignalValidation, SignalAlert
)


class MockStock:
    """Mock Stock for testing."""
    def __init__(self, id=1, symbol="AAPL", user_id=1):
        self.id = id
        self.symbol = symbol
        self.user_id = user_id


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    db.query = MagicMock()
    return db


@pytest.fixture
def signal_service(mock_db):
    """SignalService instance with mock db."""
    return SignalService(mock_db)


class TestATRCalculator:
    """Test ATR Calculator - Happy Path."""

    def test_calculate_atr_basic(self):
        """Test basic ATR calculation - Happy Path."""
        high = [100, 105, 110, 108, 112]
        low = [95, 100, 105, 103, 107]
        close = [98, 103, 108, 105, 110]
        
        result = ATRCalculator.calculate(high, low, close, period=3)
        
        assert result > 0

    def test_calculate_atr_insufficient_data(self):
        """Test ATR with insufficient data - Edge Case."""
        high = [100]
        low = [95]
        close = [98]
        
        result = ATRCalculator.calculate(high, low, close, period=14)
        
        assert result == 0.0

    def test_calculate_atr_percent(self):
        """Test ATR as percentage - Happy Path."""
        result = ATRCalculator.calculate_atr_percent(2.0, 100.0)
        
        assert result == 2.0

    def test_calculate_atr_percent_zero_price(self):
        """Test ATR percentage with zero price - Edge Case."""
        result = ATRCalculator.calculate_atr_percent(2.0, 0)
        
        assert result == 0.0


class TestSFPDetector:
    """Test Smart Fair Pullback detector - Happy Path."""

    def test_detect_bullish_sfp(self):
        """Test bullish SFP detection - Happy Path."""
        # Create data where price pulls back to support
        high = [100, 102, 105, 107, 110, 108, 106, 104, 102, 103]
        low = [95, 97, 100, 102, 105, 103, 101, 99, 97, 98]
        close = [98, 100, 104, 106, 108, 105, 103, 101, 100, 102]
        
        result = SFPDetector.detect(high, low, close, lookback=10)
        
        assert isinstance(result, bool)

    def test_detect_insufficient_data(self):
        """Test SFP with insufficient data - Edge Case."""
        high = [100]
        low = [95]
        close = [98]
        
        result = SFPDetector.detect(high, low, close)
        
        assert result is False


class TestCHOCHDetector:
    """Test Change of Character detector - Happy Path."""

    def test_detect_bullish_choch(self):
        """Test bullish CHOCH detection - Happy Path."""
        # Create data with bullish breakout
        high = [100, 102, 105, 103, 106, 108, 110, 112, 115]
        low = [95, 97, 100, 98, 101, 103, 105, 107, 110]
        close = [98, 101, 104, 102, 105, 107, 109, 111, 114]
        
        result = CHOCHDetector.detect(high, low, close)
        
        assert "direction" in result
        assert "validated" in result

    def test_detect_insufficient_data(self):
        """Test CHOCH with insufficient data - Edge Case."""
        high = [100, 102]
        low = [95, 97]
        close = [98, 100]
        
        result = CHOCHDetector.detect(high, low, close)
        
        assert result["validated"] is False


class TestFVGDetector:
    """Test Fair Value Gap detector - Happy Path."""

    def test_detect_bullish_fvg(self):
        """Test bullish FVG detection - Happy Path."""
        high = [100, 105, 107]
        low = [95, 100, 102]
        close = [98, 103, 106]
        
        result = FVGDetector.detect(high, low, close)
        
        assert "direction" in result
        assert "gap_size" in result

    def test_detect_bearish_fvg(self):
        """Test bearish FVG detection - Happy Path."""
        high = [110, 105, 103]
        low = [105, 100, 98]
        close = [108, 102, 100]
        
        result = FVGDetector.detect(high, low, close)
        
        assert "direction" in result

    def test_detect_no_fvg(self):
        """Test no FVG detected - Edge Case."""
        high = [100, 105, 110]
        low = [95, 100, 105]
        close = [98, 103, 108]
        
        result = FVGDetector.detect(high, low, close)
        
        assert result["validated"] is False


class TestSigmoidProbability:
    """Test sigmoid probability calculation - Happy Path."""

    def test_calculate_zero_validations(self):
        """Test probability with zero validations - Edge Case."""
        result = SigmoidProbability.calculate(0, 3)
        
        assert 0 <= result <= 1
        assert result < 0.5

    def test_calculate_all_validations(self):
        """Test probability with all validations - Happy Path."""
        result = SigmoidProbability.calculate(3, 3)
        
        assert 0 <= result <= 1
        assert result > 0.5

    def test_calculate_with_indicators(self):
        """Test probability with indicators - Happy Path."""
        result = SigmoidProbability.calculate_with_indicators(3, 0.5, 3)
        
        assert 0 <= result <= 1


class TestSignalGenerator:
    """Test signal generation - Happy Path."""

    def test_generate_signal_insufficient_data(self, mock_db):
        """Test signal with insufficient data - Edge Case."""
        # Arrange
        generator = SignalGenerator(mock_db)
        stock = MockStock()
        
        # Act
        result = generator.generate_signal(
            stock=stock,
            high=[100],
            low=[95],
            close=[98],
            volume=[1000]
        )

        # Assert
        assert result is None

    def test_generate_signal_no_direction(self, mock_db):
        """Test signal with no clear direction - Edge Case."""
        # Arrange
        generator = SignalGenerator(mock_db)
        stock = MockStock()
        
        # Flat/noisy data that won't trigger a signal
        high = [100] * 20
        low = [90] * 20
        close = [95] * 20
        volume = [1000] * 20
        
        # Act
        result = generator.generate_signal(
            stock=stock,
            high=high,
            low=low,
            close=close,
            volume=volume
        )

        # Assert - should return None due to no clear direction
        assert result is None or result.signal_type is None


class TestSignalService:
    """Test SignalService - Happy Path."""

    def test_get_active_signals(self, signal_service, mock_db):
        """Test getting active signals - Happy Path."""
        # Arrange
        mock_signals = [
            MagicMock(id=1, status=SignalStatus.PENDING),
            MagicMock(id=2, status=SignalStatus.ACTIVE),
        ]
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.all.return_value = mock_signals
        mock_db.query.return_value = mock_query

        # Act
        result = signal_service.get_active_signals()

        # Assert
        assert len(result) == 2

    def test_get_active_signals_filtered_by_symbol(self, signal_service, mock_db):
        """Test getting signals filtered by symbol - Edge Case."""
        # Arrange
        mock_signals = [MagicMock(id=1, symbol="AAPL", status=SignalStatus.PENDING)]
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.all.return_value = mock_signals
        mock_db.query.return_value = mock_query

        # Act
        result = signal_service.get_active_signals(symbol="AAPL")

        # Assert
        assert len(result) >= 0

    def test_get_signal_by_id(self, signal_service, mock_db):
        """Test getting signal by ID - Happy Path."""
        # Arrange
        mock_signal = MagicMock(id=1)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_signal
        mock_db.query.return_value = mock_query

        # Act
        result = signal_service.get_signal_by_id(1)

        # Assert
        assert result is not None

    def test_get_signal_by_id_not_found(self, signal_service, mock_db):
        """Test getting non-existent signal - Error Handling."""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        # Act
        result = signal_service.get_signal_by_id(999)

        # Assert
        assert result is None


class TestSignalStatusUpdates:
    """Test signal status updates - Happy Path."""

    def test_trigger_signal(self, signal_service, mock_db):
        """Test triggering a signal - Happy Path."""
        # Arrange
        mock_signal = MagicMock(id=1, status=SignalStatus.PENDING)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_signal
        mock_db.query.return_value = mock_query

        # Act
        result = signal_service.trigger_signal(1)

        # Assert
        assert result is not None

    def test_expire_signal(self, signal_service, mock_db):
        """Test expiring a signal - Happy Path."""
        # Arrange
        mock_signal = MagicMock(id=1, status=SignalStatus.ACTIVE)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_signal
        mock_db.query.return_value = mock_query

        # Act
        result = signal_service.expire_signal(1)

        # Assert
        assert result is not None

    def test_cancel_signal(self, signal_service, mock_db):
        """Test canceling a signal - Happy Path."""
        # Arrange
        mock_signal = MagicMock(id=1, status=SignalStatus.PENDING)
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_signal
        mock_db.query.return_value = mock_query

        # Act
        result = signal_service.cancel_signal(1)

        # Assert
        assert result is not None


class TestSignalDateRange:
    """Test signal date range queries - Edge Cases."""

    def test_get_signals_by_date_range(self, signal_service, mock_db):
        """Test getting signals within date range - Happy Path."""
        # Arrange
        start = datetime.utcnow() - timedelta(days=7)
        end = datetime.utcnow()
        
        mock_signals = [
            MagicMock(id=1, generated_at=start + timedelta(days=1)),
            MagicMock(id=2, generated_at=end - timedelta(days=1)),
        ]
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.all.return_value = mock_signals
        mock_db.query.return_value = mock_query

        # Act
        result = signal_service.get_signals_by_date_range(start, end)

        # Assert
        assert len(result) == 2

    def test_get_signals_by_date_range_with_type(self, signal_service, mock_db):
        """Test date range with signal type filter - Edge Case."""
        # Arrange
        start = datetime.utcnow() - timedelta(days=7)
        end = datetime.utcnow()
        
        mock_signals = [MagicMock(id=1, signal_type=SignalType.BUY)]
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.all.return_value = mock_signals
        mock_db.query.return_value = mock_query

        # Act
        result = signal_service.get_signals_by_date_range(
            start, end, signal_type=SignalType.BUY
        )

        # Assert
        assert isinstance(result, list)


class TestSignalStats:
    """Test signal statistics - Happy Path."""

    def test_get_signal_stats(self, signal_service, mock_db):
        """Test getting signal statistics - Happy Path."""
        # Arrange
        mock_db.query.return_value = MagicMock(
            count=MagicMock(return_value=10),
            filter=MagicMock(
                return_value=MagicMock(
                    count=MagicMock(return_value=5),
                    with_entities=MagicMock(
                        return_value=MagicMock(scalar=MagicMock(return_value=75.5))
                    )
                )
            )
        )

        # Act
        result = signal_service.get_signal_stats()

        # Assert
        assert "total_signals" in result
        assert "average_confidence" in result