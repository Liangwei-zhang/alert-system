"""
Tests for OHLCV Import Service.
Tested by: Admin Team
Original developer: Market Data Team
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from domains.market_data.ohlcv_import_service import OhlcvImportService
from domains.market_data.schemas import OhlcvBase, OhlcvBatchCreate


class TestOhlcvImportService:
    """Test OhlcvImportService functionality."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def import_service(self, mock_session):
        """Create import service with mock session."""
        return OhlcvImportService(mock_session)

    def test_service_initialization(self, import_service, mock_session):
        """Test service initializes with correct dependencies."""
        assert import_service.session == mock_session
        assert hasattr(import_service, 'symbol_repo')
        assert hasattr(import_service, 'ohlcv_repo')

    @pytest.mark.asyncio
    async def test_import_ohlcv_symbol_not_found(self, import_service):
        """Test import when symbol doesn't exist."""
        import_service.symbol_repo.get_by_symbol = AsyncMock(return_value=None)
        
        result = await import_service.import_ohlcv(
            symbol="INVALID",
            timeframe="1d",
            data=[],
        )
        
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_import_ohlcv_empty_data(self, import_service):
        """Test import with empty data list."""
        mock_symbol = MagicMock()
        mock_symbol.id = 1
        
        import_service.symbol_repo.get_by_symbol = AsyncMock(return_value=mock_symbol)
        import_service.symbol_repo.update = AsyncMock()
        
        result = await import_service.import_ohlcv(
            symbol="AAPL",
            timeframe="1d",
            data=[],
        )
        
        assert result["success"] is True
        assert result["total_records"] == 0
        assert result["imported"] == 0

    @pytest.mark.asyncio
    async def test_import_ohlcv_with_data(self, import_service):
        """Test import with valid OHLCV data."""
        mock_symbol = MagicMock()
        mock_symbol.id = 1
        
        import_service.symbol_repo.get_by_symbol = AsyncMock(return_value=mock_symbol)
        import_service.symbol_repo.update = AsyncMock()
        import_service.ohlcv_repo.create = AsyncMock(return_value=MagicMock())
        
        data = [
            {
                "timestamp": "2024-01-15",
                "open": 150.0,
                "high": 155.0,
                "low": 148.0,
                "close": 152.5,
                "volume": 1000000,
            }
        ]
        
        result = await import_service.import_ohlcv(
            symbol="AAPL",
            timeframe="1d",
            data=data,
        )
        
        assert result["success"] is True
        assert result["symbol"] == "AAPL"

    def test_validate_record_valid(self, import_service):
        """Test validating a valid OHLCV record."""
        record = {
            "timestamp": "2024-01-15",
            "open": 150.0,
            "high": 155.0,
            "low": 148.0,
            "close": 152.5,
            "volume": 1000000,
        }
        
        assert import_service._validate_record(record) is True

    def test_validate_record_missing_fields(self, import_service):
        """Test validating record with missing required fields."""
        record = {
            "timestamp": "2024-01-15",
            "open": 150.0,
            "high": 155.0,
            "low": 148.0,
            # missing close and volume
        }
        
        assert import_service._validate_record(record) is False

    def test_validate_record_negative_price(self, import_service):
        """Test validating record with negative price."""
        record = {
            "timestamp": "2024-01-15",
            "open": -10.0,
            "high": 155.0,
            "low": 148.0,
            "close": 152.5,
            "volume": 1000000,
        }
        
        assert import_service._validate_record(record) is False

    def test_validate_record_high_less_than_low(self, import_service):
        """Test validating record where high < low."""
        record = {
            "timestamp": "2024-01-15",
            "open": 150.0,
            "high": 140.0,
            "low": 148.0,
            "close": 152.5,
            "volume": 1000000,
        }
        
        assert import_service._validate_record(record) is False

    def test_parse_timestamp_datetime(self, import_service):
        """Test parsing timestamp from datetime object."""
        ts = datetime(2024, 1, 15, 10, 30, 0)
        result = import_service._parse_timestamp(ts)
        assert result == ts

    def test_parse_timestamp_string_iso(self, import_service):
        """Test parsing timestamp from ISO string."""
        result = import_service._parse_timestamp("2024-01-15T10:30:00")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_timestamp_string_with_z(self, import_service):
        """Test parsing timestamp from string with Z suffix."""
        result = import_service._parse_timestamp("2024-01-15T10:30:00Z")
        assert result is not None

    def test_parse_timestamp_invalid(self, import_service):
        """Test parsing invalid timestamp."""
        result = import_service._parse_timestamp("invalid")
        assert result is None

    @pytest.mark.asyncio
    async def test_import_from_yahoo(self, import_service):
        """Test Yahoo import placeholder."""
        result = await import_service.import_from_yahoo(
            symbol="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_get_import_status(self, import_service):
        """Test getting import status."""
        mock_symbol = MagicMock()
        mock_symbol.id = 1
        mock_symbol.last_sync_at = datetime(2024, 1, 15)
        
        mock_ohlcv = MagicMock()
        mock_ohlcv.timestamp = datetime(2024, 1, 15)
        
        import_service.symbol_repo.get_by_symbol = AsyncMock(return_value=mock_symbol)
        import_service.ohlcv_repo.get_latest = AsyncMock(return_value=mock_ohlcv)
        import_service.ohlcv_repo.get_oldest = AsyncMock(return_value=mock_ohlcv)
        import_service.ohlcv_repo.count = AsyncMock(return_value=100)
        
        result = await import_service.get_import_status("AAPL", "1d")
        
        assert result is not None
        assert result["symbol"] == "AAPL"
        assert result["total_records"] == 100

    @pytest.mark.asyncio
    async def test_delete_range(self, import_service):
        """Test deleting OHLCV data in range."""
        mock_symbol = MagicMock()
        mock_symbol.id = 1
        
        import_service.symbol_repo.get_by_symbol = AsyncMock(return_value=mock_symbol)
        import_service.ohlcv_repo.delete_range = AsyncMock(return_value=50)
        
        result = await import_service.delete_range(
            symbol="AAPL",
            timeframe="1d",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        
        assert result["success"] is True
        assert result["deleted"] == 50


class TestImportSchemas:
    """Test import-related Pydantic schemas."""

    def test_ohlcv_batch_create(self):
        """Test OhlcvBatchCreate schema."""
        data = [
            OhlcvBase(
                timestamp=datetime(2024, 1, 15),
                open=150.0,
                high=155.0,
                low=148.0,
                close=152.5,
                volume=1000000,
            )
        ]
        
        batch = OhlcvBatchCreate(
            symbol="AAPL",
            timeframe="1d",
            data=data,
            source="yahoo",
        )
        
        assert batch.symbol == "AAPL"
        assert batch.timeframe == "1d"
        assert len(batch.data) == 1
        assert batch.source == "yahoo"

    def test_ohlcv_batch_create_default_source(self):
        """Test OhlcvBatchCreate with default source."""
        batch = OhlcvBatchCreate(
            symbol="AAPL",
            data=[],
        )
        
        assert batch.source == "yahoo"
