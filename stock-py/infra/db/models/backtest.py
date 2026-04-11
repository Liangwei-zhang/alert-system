from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from infra.db.models.base import Base, sql_enum


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BacktestRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BacktestRunModel(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_name: Mapped[str] = mapped_column(String(100), index=True)
    experiment_name: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    run_key: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    symbol: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    timeframe: Mapped[str] = mapped_column(String(16), default="1d", index=True)
    window_days: Mapped[int] = mapped_column(Integer, default=0, index=True)
    status: Mapped[BacktestRunStatus] = mapped_column(
        sql_enum(BacktestRunStatus, name="backtestrunstatus"),
        default=BacktestRunStatus.PENDING,
        server_default=BacktestRunStatus.PENDING.value,
        index=True,
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifacts: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dataset_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StrategyRankingModel(Base):
    __tablename__ = "strategy_rankings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_name: Mapped[str] = mapped_column(String(100), index=True)
    timeframe: Mapped[str] = mapped_column(String(16), default="1d", index=True)
    rank: Mapped[int] = mapped_column(Integer, index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    degradation: Mapped[float] = mapped_column(Float, default=0.0)
    symbols_covered: Mapped[int] = mapped_column(Integer, default=0)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    as_of_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        index=True,
    )


__all__ = [
    "BacktestRunModel",
    "BacktestRunStatus",
    "StrategyRankingModel",
]
