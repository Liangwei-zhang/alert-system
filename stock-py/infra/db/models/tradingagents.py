"""
TradingAgents database models.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from infra.db.models.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TradingAgentsStatus(str, Enum):
    """TradingAgents job status."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class TriggerType(str, Enum):
    """Type of trigger that initiated the request."""

    SCANNER = "scanner"
    MANUAL = "manual"
    POSITION_REVIEW = "position_review"
    SCHEDULED = "scheduled"


class FinalAction(str, Enum):
    """Final action from TradingAgents analysis."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    NO_ACTION = "no_action"
    UNKNOWN = "unknown"


class TradingAgentsAnalysisRecord(Base):
    """Record of TradingAgents analysis requests and results."""

    __tablename__ = "tradingagents_analysis_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Request identifiers
    request_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    job_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # Request details
    ticker: Mapped[str] = mapped_column(String(10), index=True)
    analysis_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    selected_analysts: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    trigger_type: Mapped[TriggerType] = mapped_column(String(20), index=True)
    trigger_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON

    # Projection/result
    tradingagents_status: Mapped[TradingAgentsStatus] = mapped_column(
        String(20), default=TradingAgentsStatus.PENDING, index=True
    )
    final_action: Mapped[Optional[FinalAction]] = mapped_column(String(20), nullable=True)
    decision_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Full JSON response

    # Timing
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delayed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )

    # Metadata
    poll_count: Mapped[int] = mapped_column(Integer, default=0)
    last_poll_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    webhook_received: Mapped[bool] = mapped_column(Boolean, default=False)

    # Indexes
    __table_args__ = (
        Index("ix_ta_records_status_date", "tradingagents_status", "created_at"),
        Index("ix_ta_records_ticker_status", "ticker", "tradingagents_status"),
    )


class TradingAgentsSubmitFailure(Base):
    """Record of submit failures for retry logic."""

    __tablename__ = "tradingagents_submit_failures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Link to original request
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    ticker: Mapped[str] = mapped_column(String(10))

    # Failure details
    error_message: Mapped[str] = mapped_column(Text)
    error_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)

    # Status
    resolved: Mapped[bool] = mapped_column(default=False, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        index=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Retry info
    last_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # Indexes
    __table_args__ = (Index("ix_ta_failures_unresolved", "resolved", "next_retry_at"),)


__all__ = [
    "FinalAction",
    "TradingAgentsAnalysisRecord",
    "TradingAgentsStatus",
    "TradingAgentsSubmitFailure",
    "TriggerType",
]
