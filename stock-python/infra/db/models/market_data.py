"""
Market data database models.
"""
from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, Numeric, Integer, ForeignKey, Enum as SQLEnum, Index, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infra.database import Base


class AssetType(str, Enum):
    """Asset type enumeration."""
    STOCK = "stock"
    ETF = "etf"
    INDEX = "index"
    CRYPTO = "crypto"
    FOREX = "forex"


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


class SymbolStatus(str, Enum):
    """Symbol status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELISTED = "delisted"
    SUSPENDED = "suspended"


class SymbolModel(Base):
    """Symbol metadata model."""

    __tablename__ = "symbols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    exchange: Mapped[str] = mapped_column(String(50), index=True)
    asset_type: Mapped[AssetType] = mapped_column(SQLEnum(AssetType), default=AssetType.STOCK)
    status: Mapped[SymbolStatus] = mapped_column(SQLEnum(SymbolStatus), default=SymbolStatus.ACTIVE)
    
    # Optional fields
    sector: Mapped[str] = mapped_column(String(100), nullable=True)
    industry: Mapped[str] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(50), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    
    # Market data
    market_cap: Mapped[float] = mapped_column(Numeric(20, 2), nullable=True)
    
    # External IDs
    isin: Mapped[str] = mapped_column(String(20), nullable=True)
    cusip: Mapped[str] = mapped_column(String(20), nullable=True)
    sedol: Mapped[str] = mapped_column(String(20), nullable=True)
    
    # Data source
    data_source: Mapped[str] = mapped_column(String(50), nullable=True)
    external_id: Mapped[str] = mapped_column(String(100), nullable=True)
    
    # Metadata
    last_sync_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    ohlcv_data: Mapped[list["OhlcvModel"]] = relationship(
        "OhlcvModel", back_populates="symbol", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_symbol_exchange", "symbol", "exchange"),
        Index("idx_symbol_status", "status"),
        Index("idx_symbol_asset_type", "asset_type"),
    )


class OhlcvModel(Base):
    """OHLCV (Open, High, Low, Close, Volume) candlestick data model."""

    __tablename__ = "ohlcv"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("symbols.id"), index=True, nullable=False
    )
    
    # Time period
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), default="1d")  # 1m, 5m, 1h, 1d, 1w
    
    # OHLCV fields
    open: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Calculated fields
    adjusted_close: Mapped[float] = mapped_column(Numeric(18, 8), nullable=True)
    dividends: Mapped[float] = mapped_column(Numeric(18, 8), nullable=True)
    splits: Mapped[float] = mapped_column(Numeric(10, 4), nullable=True)
    
    # Data quality
    is_adjusted: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(50), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    symbol: Mapped["SymbolModel"] = relationship("SymbolModel", back_populates="ohlcv_data")

    __table_args__ = (
        Index("idx_ohlcv_symbol_time", "symbol_id", "timestamp", "timeframe"),
        Index("idx_ohlcv_timeframe", "timeframe"),
        UniqueConstraint("symbol_id", "timestamp", "timeframe", name="uix_ohlcv_symbol_timeframe"),
    )


class OhlcvAnomalyModel(Base):
    """OHLCV data quality anomaly tracking model."""

    __tablename__ = "ohlcv_anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ohlcv_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ohlcv.id"), index=True, nullable=True
    )
    symbol_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("symbols.id"), index=True, nullable=False
    )
    
    # Anomaly details
    anomaly_type: Mapped[AnomalyType] = mapped_column(SQLEnum(AnomalyType), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="medium")  # low, medium, high, critical
    
    # Details
    field_name: Mapped[str] = mapped_column(String(50), nullable=True)
    expected_value: Mapped[str] = mapped_column(String(100), nullable=True)
    actual_value: Mapped[str] = mapped_column(String(100), nullable=True)
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    
    # Resolution
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    resolution_notes: Mapped[str] = mapped_column(String(500), nullable=True)
    
    # Timestamps
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_anomaly_symbol", "symbol_id", "is_resolved"),
        Index("idx_anomaly_type", "anomaly_type"),
    )