from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from infra.db.models.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PortfolioPositionModel(Base):
    __tablename__ = "user_portfolio"
    __table_args__ = (
        UniqueConstraint("user_id", "symbol", name="uq_user_portfolio_symbol"),
        Index("ix_user_portfolio_notify_symbol", "notify", "symbol"),
        Index("ix_user_portfolio_user_total_capital", "user_id", "total_capital"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    avg_cost: Mapped[float] = mapped_column(Numeric(15, 4), default=0)
    total_capital: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    target_profit: Mapped[float] = mapped_column(Numeric(8, 4), default=0.15)
    stop_loss: Mapped[float] = mapped_column(Numeric(8, 4), default=0.08)
    notify: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )
