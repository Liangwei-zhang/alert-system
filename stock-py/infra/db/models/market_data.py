from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from infra.db.models.base import Base
from infra.db.models.symbols import SymbolModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OhlcvModel(Base):
    __tablename__ = "ohlcv"
    __table_args__ = (
        UniqueConstraint(
            "symbol", "timeframe", "bar_time", name="uq_ohlcv_symbol_timeframe_bar_time"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol_id: Mapped[int | None] = mapped_column(
        ForeignKey("symbols.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    timeframe: Mapped[str] = mapped_column(String(16), index=True)
    bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[float] = mapped_column(Numeric(24, 6))
    high: Mapped[float] = mapped_column(Numeric(24, 6))
    low: Mapped[float] = mapped_column(Numeric(24, 6))
    close: Mapped[float] = mapped_column(Numeric(24, 6))
    volume: Mapped[float] = mapped_column(Numeric(20, 4), default=0)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        index=True,
    )


class OhlcvAnomalyModel(Base):
    __tablename__ = "ohlcv_anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    timeframe: Mapped[str] = mapped_column(String(16), index=True)
    bar_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    anomaly_code: Mapped[str] = mapped_column(String(50), index=True)
    severity: Mapped[str] = mapped_column(String(20), default="warning", index=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quarantined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        index=True,
    )


__all__ = ["OhlcvAnomalyModel", "OhlcvModel", "SymbolModel"]
