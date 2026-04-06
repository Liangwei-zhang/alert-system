"""
Market data schemas for API requests/responses.
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator


class AssetType(str, Enum):
    """Asset type enumeration."""
    STOCK = "stock"
    ETF = "etf"
    INDEX = "index"
    CRYPTO = "crypto"
    FOREX = "forex"


class SymbolStatus(str, Enum):
    """Symbol status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELISTED = "delisted"
    SUSPENDED = "suspended"


class Timeframe(str, Enum):
    """OHLCV timeframe enumeration."""
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    WEEK_1 = "1w"


# ============================================
# Symbol Schemas
# ============================================


class SymbolBase(BaseModel):
    """Base symbol schema."""
    symbol: str = Field(..., max_length=20)
    name: str = Field(..., max_length=200)
    exchange: Optional[str] = Field(None, max_length=50)
    asset_type: AssetType = AssetType.STOCK
    sector: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=50)
    currency: str = "USD"
    market_cap: Optional[float] = None
    isin: Optional[str] = Field(None, max_length=20)
    cusip: Optional[str] = Field(None, max_length=20)
    data_source: Optional[str] = Field(None, max_length=50)


class SymbolCreate(SymbolBase):
    """Schema for creating a symbol."""
    external_id: Optional[str] = Field(None, max_length=100)


class SymbolUpdate(BaseModel):
    """Schema for updating a symbol."""
    name: Optional[str] = Field(None, max_length=200)
    exchange: Optional[str] = Field(None, max_length=50)
    asset_type: Optional[AssetType] = None
    status: Optional[SymbolStatus] = None
    sector: Optional[str] = Field(None, max_length=100)
    industry: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=50)
    currency: Optional[str] = Field(None, max_length=10)
    market_cap: Optional[float] = None
    is_verified: Optional[bool] = None
    last_sync_at: Optional[datetime] = None


class SymbolResponse(SymbolBase):
    """Schema for symbol response."""
    id: int
    status: SymbolStatus = SymbolStatus.ACTIVE
    external_id: Optional[str] = None
    is_verified: bool = False
    last_sync_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SymbolSearchRequest(BaseModel):
    """Schema for symbol search request."""
    query: str = Field(..., min_length=1, max_length=100)
    exchange: Optional[str] = None
    asset_type: Optional[AssetType] = None
    limit: int = Field(default=20, ge=1, le=100)


class SymbolSearchResult(BaseModel):
    """Schema for symbol search result."""
    symbol: str
    name: str
    exchange: Optional[str] = None
    asset_type: AssetType = AssetType.STOCK

    model_config = {"from_attributes": True}


# ============================================
# OHLCV Schemas
# ============================================


class OhlcvBase(BaseModel):
    """Base OHLCV schema."""
    timestamp: datetime
    timeframe: str = Field(default="1d", max_length=10)
    open: float
    high: float
    low: float
    close: float
    volume: int = Field(ge=0)
    adjusted_close: Optional[float] = None
    dividends: Optional[float] = None
    splits: Optional[float] = None
    is_adjusted: bool = False
    source: Optional[str] = Field(None, max_length=50)

    @field_validator("high", "low")
    @classmethod
    def validate_prices(cls, v, info):
        if v is not None and v < 0:
            raise ValueError(f"{info.field_name} must be non-negative")
        return v

    @field_validator("high")
    @classmethod
    def validate_high(cls, v, info, values):
        if v is not None and "low" in values and v < values["low"]:
            raise ValueError("high must be >= low")
        return v


class OhlcvCreate(OhlcvBase):
    """Schema for creating OHLCV data."""
    symbol_id: int
    symbol: Optional[str] = None  # For batch import


class OhlcvUpdate(BaseModel):
    """Schema for updating OHLCV data."""
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None
    adjusted_close: Optional[float] = None
    is_adjusted: Optional[bool] = None


class OhlcvResponse(OhlcvBase):
    """Schema for OHLCV response."""
    id: int
    symbol_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class OhlcvBatchCreate(BaseModel):
    """Schema for batch OHLCV import."""
    symbol: str
    timeframe: str = "1d"
    data: List[OhlcvBase]
    source: Optional[str] = "yahoo"


class OhlcvQueryRequest(BaseModel):
    """Schema for OHLCV query request."""
    symbol: str
    timeframe: str = "1d"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = Field(default=100, ge=1, le=5000)


class OhlcvQueryResponse(BaseModel):
    """Schema for OHLCV query response."""
    symbol: str
    symbol_id: int
    timeframe: str
    data: List[OhlcvResponse]
    total: int
    has_more: bool = False


# ============================================
# Quality Schemas
# ============================================


class AnomalyType(str, Enum):
    """OHLCV anomaly type enumeration."""
    MISSING_DATA = "missing_data"
    DUPLICATE_TIMESTAMP = "duplicate_timestamp"
    PRICE_SPIKE = "price_spike"
    VOLUME_SPIKE = "volume_spike"
    INVALID_PRICE = "invalid_price"
    NEGATIVE_PRICE = "negative_price"
    ZERO_VOLUME = "zero_volume"
    GAP = "gap"


class AnomalySeverity(str, Enum):
    """Anomaly severity enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OhlcvAnomalyBase(BaseModel):
    """Base OHLCV anomaly schema."""
    anomaly_type: AnomalyType
    severity: AnomalySeverity = AnomalySeverity.MEDIUM
    field_name: Optional[str] = None
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    description: Optional[str] = None


class OhlcvAnomalyCreate(OhlcvAnomalyBase):
    """Schema for creating an anomaly."""
    ohlcv_id: Optional[int] = None
    symbol_id: int


class OhlcvAnomalyResponse(OhlcvAnomalyBase):
    """Schema for anomaly response."""
    id: int
    ohlcv_id: Optional[int] = None
    symbol_id: int
    is_resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    detected_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class QualityCheckRequest(BaseModel):
    """Schema for quality check request."""
    symbol: str
    start_date: datetime
    end_date: datetime
    timeframe: str = "1d"


class QualityCheckResponse(BaseModel):
    """Schema for quality check response."""
    symbol: str
    total_records: int
    anomalies_count: int
    anomalies: List[OhlcvAnomalyResponse]
    quality_score: float  # 0-100