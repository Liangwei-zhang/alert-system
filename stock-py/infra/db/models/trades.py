from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from infra.db.models.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TradeStatus(str, Enum):
    """Trade status."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    ADJUSTED = "adjusted"
    IGNORED = "ignored"
    EXPIRED = "expired"


class TradeAction(str, Enum):
    """Trade action type."""

    BUY = "buy"
    SELL = "sell"
    ADD = "add"


class TradeLogModel(Base):
    """Trade log model for tracking trade confirmations."""

    __tablename__ = "trade_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(10), index=True)
    action: Mapped[TradeAction] = mapped_column(SQLEnum(TradeAction), index=True)
    suggested_shares: Mapped[float] = mapped_column(Numeric(15, 4))
    suggested_price: Mapped[float] = mapped_column(Numeric(12, 4))
    suggested_amount: Mapped[float] = mapped_column(Numeric(15, 2))
    actual_shares: Mapped[float | None] = mapped_column(Numeric(15, 4), nullable=True)
    actual_price: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    actual_amount: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)
    status: Mapped[TradeStatus] = mapped_column(
        SQLEnum(TradeStatus),
        default=TradeStatus.PENDING,
        server_default=TradeStatus.PENDING.value,
        index=True,
    )
    link_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    link_sig: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    extra: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_by_operator_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_operators.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_trade_log_user_status", "user_id", "status"),
        Index("ix_trade_log_user_symbol", "user_id", "symbol"),
    )


Trade = TradeLogModel

__all__ = ["Trade", "TradeAction", "TradeLogModel", "TradeStatus"]
