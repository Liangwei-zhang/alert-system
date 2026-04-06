"""
Stock model - extended with watchlist support.
"""
from datetime import datetime

from sqlalchemy import String, DateTime, Numeric, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infra.database import Base


class Stock(Base):
    """Stock model for stock data."""

    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    exchange: Mapped[str] = mapped_column(String(50))
    sector: Mapped[str] = mapped_column(String(100), nullable=True)
    current_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    previous_close: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    volume: Mapped[int] = mapped_column(Integer, default=0)
    market_cap: Mapped[float] = mapped_column(Numeric(20, 2), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    watchlist_items: Mapped[list["WatchlistItem"]] = relationship(
        "WatchlistItem", back_populates="stock"
    )
    signals: Mapped[list["Signal"]] = relationship("Signal", back_populates="stock")


class Watchlist(Base):
    """User watchlist model."""

    __tablename__ = "watchlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    items: Mapped[list["WatchlistItem"]] = relationship(
        "WatchlistItem", back_populates="watchlist", cascade="all, delete-orphan"
    )


class WatchlistItem(Base):
    """Watchlist item model - links stocks to watchlists."""

    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("watchlist_id", "stock_id", name="uq_watchlist_stock"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("watchlists.id", ondelete="CASCADE"), index=True
    )
    stock_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stocks.id", ondelete="CASCADE"), index=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[str] = mapped_column(String(500), nullable=True)

    # Relationships
    watchlist: Mapped["Watchlist"] = relationship("Watchlist", back_populates="items")
    stock: Mapped["Stock"] = relationship("Stock", back_populates="watchlist_items")


# Pydantic schemas for API
from pydantic import BaseModel, ConfigDict
from typing import Optional


class StockBase(BaseModel):
    """Base stock schema."""
    symbol: str
    name: str
    exchange: str = "NASDAQ"
    sector: Optional[str] = None


class StockCreate(StockBase):
    """Stock creation schema."""
    pass


class StockUpdate(BaseModel):
    """Stock update schema."""
    name: Optional[str] = None
    exchange: Optional[str] = None
    sector: Optional[str] = None
    current_price: Optional[float] = None
    previous_close: Optional[float] = None
    volume: Optional[int] = None
    market_cap: Optional[float] = None


class StockResponse(StockBase):
    """Stock response schema."""
    id: int
    current_price: Optional[float] = None
    previous_close: Optional[float] = None
    volume: int = 0
    market_cap: Optional[float] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StockWithPrice(BaseModel):
    """Stock with real-time price from cache/API."""
    symbol: str
    name: str
    exchange: str
    price: float
    change: float
    change_percent: float
    volume: int
    updated_at: datetime


class WatchlistBase(BaseModel):
    """Base watchlist schema."""
    name: str


class WatchlistCreate(WatchlistBase):
    """Watchlist creation schema."""
    pass


class WatchlistResponse(WatchlistBase):
    """Watchlist response schema."""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WatchlistItemResponse(BaseModel):
    """Watchlist item with stock details."""
    id: int
    stock: StockResponse
    notes: Optional[str] = None
    added_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WatchlistDetailResponse(WatchlistResponse):
    """Watchlist with all items."""
    items: list[WatchlistItemResponse] = []

class StockQuote(BaseModel):
    """Stock price quote."""
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    volume: int
    timestamp: Optional[datetime] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None


class StockSearchResult(BaseModel):
    """Stock search result."""
    symbol: str
    name: str
    exchange: Optional[str] = None
    type: Optional[str] = None


class HistoricalData(BaseModel):
    """Historical stock data."""
    symbol: str
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
