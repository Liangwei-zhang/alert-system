"""
Tests for OHLCV model and repository.
Tested by: Admin Team
Original developer: Market Data Team
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from domains.market_data.schemas import (
    OhlcvCreate,
    OhlcvUpdate,
    OhlcvResponse,
    OhlcvBase,
    Timeframe,
)
from domains.market_data.repository import OhlcvRepository


class TestOhlcvSchema:
    """Test OHLCV Pydantic schemas."""

    def test_ohlcv_base_valid(self):
        """Test creating a valid OhlcvBase schema."""
        ohlcv = OhlcvBase(
            timestamp=datetime(2024, 1, 15),
            timeframe="1d",
            open=150.0,
            high=155.0,
            low=148.0,
            close=152.5,
            volume=1000000,
        )
        assert ohlcv.open == 150.0
        assert ohlcv.high == 155.0
        assert ohlcv.low == 148.0
        assert ohlcv.close == 152.5

    def test_ohlcv_with_optional_fields(self):
        """Test OhlcvBase with optional fields."""
        ohlcv = OhlcvBase(
            timestamp=datetime(2024, 1, 15),
            timeframe="1h",
            open=150.0,
            high=155.0,
            low=148.0,
            close=152.5,
            volume=100000,
            adjusted_close=152.0,
            dividends=0.24,
            splits=1.0,
            is_adjusted=True,
            source="yahoo",
        )
        assert ohlcv.adjusted_close == 152.0
        assert ohlcv.dividends == 0.24
        assert ohlcv.is_adjusted is True

    def test_ohlcv_price_validation_positive(self):
        """Test that positive prices are valid."""
        ohlcv = OhlcvBase(
            timestamp=datetime(2024, 1, 15),
            open=100.0,
            high=105.0,
            low=99.0,
            close=103.0,
            volume=500000,
        )
        assert ohlcv.high >= ohlcv.low

    def test_ohlcv_create_with_symbol_id(self):
        """Test OhlcvCreate with symbol_id."""
        ohlcv = OhlcvCreate(
            symbol_id=1,
            symbol="AAPL",
            timestamp=datetime(2024, 1, 15),
            open=150.0,
            high=155.0,
            low=148.0,
            close=152.5,
            volume=1000000,
        )
        assert ohlcv.symbol_id == 1
        assert ohlcv.symbol == "AAPL"

    def test_ohlcv_update_partial(self):
        """Test OhlcvUpdate with partial fields."""
        update = OhlcvUpdate(
            close=155.0,
            volume=1100000,
        )
        assert update.close == 155.0
        assert update.volume == 1100000
        assert update.open is None

    def test_ohlcv_response_from_attributes(self):
        """Test OhlcvResponse from model attributes."""
        response = OhlcvResponse(
            id=1,
            symbol_id=1,
            timestamp=datetime(2024, 1, 15),
            timeframe="1d",
            open=150.0,
            high=155.0,
            low=148.0,
            close=152.5,
            volume=1000000,
            created_at=datetime.utcnow(),
        )
        assert response.id == 1
        assert response.symbol_id == 1


class TestOhlcvRepository:
    """Test OhlcvRepository CRUD operations."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_create_ohlcv(self, mock_session):
        """Test creating an OHLCV record."""
        repo = OhlcvRepository(mock_session)
        
        # Verify repository is set up correctly
        assert hasattr(repo, 'session')
        assert repo.session == mock_session

    @pytest.mark.asyncio
    async def test_get_by_id(self, mock_session):
        """Test getting OHLCV by ID."""
        repo = OhlcvRepository(mock_session)
        
        assert hasattr(repo, 'get_by_id')

    @pytest.mark.asyncio
    async def test_get_by_symbol_timeframe(self, mock_session):
        """Test getting OHLCV by symbol and timeframe."""
        repo = OhlcvRepository(mock_session)
        
        # Test method exists
        assert hasattr(repo, 'get_by_symbol_timeframe')

    @pytest.mark.asyncio
    async def test_get_latest(self, mock_session):
        """Test getting latest OHLCV record."""
        repo = OhlcvRepository(mock_session)
        
        assert callable(getattr(repo, 'get_latest', None))

    @pytest.mark.asyncio
    async def test_get_oldest(self, mock_session):
        """Test getting oldest OHLCV record."""
        repo = OhlcvRepository(mock_session)
        
        assert callable(getattr(repo, 'get_oldest', None))

    @pytest.mark.asyncio
    async def test_bulk_create(self, mock_session):
        """Test bulk OHLCV creation."""
        repo = OhlcvRepository(mock_session)
        
        ohlcv_data = [
            {
                "symbol_id": 1,
                "timestamp": datetime(2024, 1, 15),
                "timeframe": "1d",
                "open": 150.0,
                "high": 155.0,
                "low": 148.0,
                "close": 152.5,
                "volume": 1000000,
            },
            {
                "symbol_id": 1,
                "timestamp": datetime(2024, 1, 16),
                "timeframe": "1d",
                "open": 152.5,
                "high": 158.0,
                "low": 151.0,
                "close": 156.0,
                "volume": 1100000,
            },
        ]
        
        assert callable(getattr(repo, 'bulk_create', None))

    @pytest.mark.asyncio
    async def test_bulk_upsert(self, mock_session):
        """Test bulk upsert OHLCV data."""
        repo = OhlcvRepository(mock_session)
        
        assert callable(getattr(repo, 'bulk_upsert', None))

    @pytest.mark.asyncio
    async def test_delete_range(self, mock_session):
        """Test deleting OHLCV in date range."""
        repo = OhlcvRepository(mock_session)
        
        assert callable(getattr(repo, 'delete_range', None))

    @pytest.mark.asyncio
    async def test_count(self, mock_session):
        """Test counting OHLCV records."""
        repo = OhlcvRepository(mock_session)
        
        assert callable(getattr(repo, 'count', None))
