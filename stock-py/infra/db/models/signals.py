from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from infra.db.models.base import Base, sql_enum


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SignalType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    SPLIT_BUY = "split_buy"
    SPLIT_SELL = "split_sell"


class SignalStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    TRIGGERED = "triggered"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class SignalValidation(str, Enum):
    SFP = "sfp"
    CHOCH = "choch"
    FVG = "fvg"
    VALIDATED = "validated"


class SignalModel(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    signal_type: Mapped[SignalType] = mapped_column(
        sql_enum(SignalType, name="signaltype"),
        index=True,
    )
    status: Mapped[SignalStatus] = mapped_column(
        sql_enum(SignalStatus, name="signalstatus"),
        default=SignalStatus.PENDING,
        server_default=SignalStatus.PENDING.value,
        index=True,
    )
    entry_price: Mapped[float] = mapped_column(Numeric(12, 4))
    stop_loss: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    take_profit_1: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    take_profit_2: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    take_profit_3: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    probability: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    risk_reward_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    sfp_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    chooch_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    fvg_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_status: Mapped[SignalValidation] = mapped_column(
        sql_enum(SignalValidation, name="signalvalidation"),
        default=SignalValidation.SFP,
        server_default=SignalValidation.SFP.value,
    )
    atr_value: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    atr_multiplier: Mapped[float] = mapped_column(Float, default=2.0)
    indicators: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        index=True,
    )
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ScannerRunModel(Base):
    __tablename__ = "scanner_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bucket_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)
    scanned_count: Mapped[int] = mapped_column(Integer, default=0)
    emitted_count: Mapped[int] = mapped_column(Integer, default=0)
    suppressed_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ScannerDecisionModel(Base):
    __tablename__ = "scanner_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    decision: Mapped[str] = mapped_column(String(32), index=True)
    reason: Mapped[str] = mapped_column(Text)
    signal_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    suppressed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        index=True,
    )


__all__ = [
    "ScannerDecisionModel",
    "ScannerRunModel",
    "SignalModel",
    "SignalStatus",
    "SignalType",
    "SignalValidation",
]
