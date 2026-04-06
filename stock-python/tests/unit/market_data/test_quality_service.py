"""
Tests for OHLCV Quality Service.
Tested by: Admin Team
Original developer: Market Data Team
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from domains.market_data.quality_service import OhlcvQualityService
from domains.market_data.schemas import (
    AnomalyType,
    AnomalySeverity,
    QualityCheckRequest,
    QualityCheckResponse,
)


class TestOhlcvQualityService:
    """Test OhlcvQualityService functionality."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def quality_service(self, mock_session):
        """Create quality service with mock session."""
        return OhlcvQualityService(mock_session)

    def test_service_initialization(self, quality_service, mock_session):
        """Test service initializes with correct dependencies."""
        assert quality_service.session == mock_session
        assert hasattr(quality_service, 'symbol_repo')
        assert hasattr(quality_service, 'ohlcv_repo')
        assert hasattr(quality_service, 'anomaly_repo')

    @pytest.mark.asyncio
    async def test_check_symbol_quality_not_found(self, quality_service):
        """Test quality check when symbol doesn't exist."""
        quality_service.symbol_repo.get_by_symbol = AsyncMock(return_value=None)
        
        result = await quality_service.check_symbol_quality(
            symbol="INVALID",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_check_symbol_quality_empty_data(self, quality_service):
        """Test quality check with no OHLCV data."""
        mock_symbol = MagicMock()
        mock_symbol.id = 1
        
        quality_service.symbol_repo.get_by_symbol = AsyncMock(return_value=mock_symbol)
        quality_service.ohlcv_repo.get_by_symbol_timeframe = AsyncMock(return_value=[])
        
        result = await quality_service.check_symbol_quality(
            symbol="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        
        assert result["success"] is True
        assert result["total_records"] == 0
        assert result["anomalies_count"] == 0
        assert result["quality_score"] == 100.0

    @pytest.mark.asyncio
    async def test_check_symbol_quality_with_data(self, quality_service):
        """Test quality check with OHLCV data."""
        mock_symbol = MagicMock()
        mock_symbol.id = 1
        
        mock_ohlcv = MagicMock()
        mock_ohlcv.id = 1
        mock_ohlcv.timestamp = datetime(2024, 1, 15)
        mock_ohlcv.open = 150.0
        mock_ohlcv.high = 155.0
        mock_ohlcv.low = 148.0
        mock_ohlcv.close = 152.5
        mock_ohlcv.volume = 1000000
        
        quality_service.symbol_repo.get_by_symbol = AsyncMock(return_value=mock_symbol)
        quality_service.ohlcv_repo.get_by_symbol_timeframe = AsyncMock(return_value=[mock_ohlcv])
        quality_service.anomaly_repo.create = AsyncMock(return_value=MagicMock())
        
        result = await quality_service.check_symbol_quality(
            symbol="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        
        assert result["success"] is True
        assert result["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_calculate_quality_score_empty(self, quality_service):
        """Test quality score calculation with no records."""
        score = quality_service._calculate_quality_score(0, 0)
        assert score == 100.0

    @pytest.mark.asyncio
    async def test_calculate_quality_score_with_anomalies(self, quality_service):
        """Test quality score calculation with anomalies."""
        score = quality_service._calculate_quality_score(100, 5)
        assert score < 100.0
        assert score >= 0

    @pytest.mark.asyncio
    async def test_resolve_anomaly(self, quality_service):
        """Test resolving an anomaly."""
        mock_anomaly = MagicMock()
        quality_service.anomaly_repo.resolve = AsyncMock(return_value=mock_anomaly)
        
        result = await quality_service.resolve_anomaly(
            anomaly_id=1,
            notes="Fixed the data issue",
        )
        
        assert result is True

    @pytest.mark.asyncio
    async def test_get_unresolved_anomalies(self, quality_service):
        """Test getting unresolved anomalies for a symbol."""
        quality_service.symbol_repo.get_by_symbol = AsyncMock(return_value=None)
        
        result = await quality_service.get_unresolved_anomalies("AAPL")
        
        assert result == []


class TestQualitySchemas:
    """Test quality-related Pydantic schemas."""

    def test_quality_check_request(self):
        """Test QualityCheckRequest schema."""
        request = QualityCheckRequest(
            symbol="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            timeframe="1d",
        )
        assert request.symbol == "AAPL"
        assert request.timeframe == "1d"

    def test_quality_check_request_default_timeframe(self):
        """Test QualityCheckRequest with default timeframe."""
        request = QualityCheckRequest(
            symbol="MSFT",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )
        assert request.timeframe == "1d"

    def test_quality_check_response(self):
        """Test QualityCheckResponse schema."""
        response = QualityCheckResponse(
            symbol="AAPL",
            total_records=100,
            anomalies_count=5,
            anomalies=[],
            quality_score=95.0,
        )
        assert response.symbol == "AAPL"
        assert response.quality_score == 95.0
