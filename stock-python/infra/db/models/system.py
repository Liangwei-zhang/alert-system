"""
Database models for system configuration and outbox events.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, Integer, Boolean, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column

from infra.database import Base


class SystemConfigModel(Base):
    """System configuration key-value store."""

    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    value_type: Mapped[str] = mapped_column(String(50), default="string")  # string, int, float, bool, json
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    updated_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    def __repr__(self):
        return f"<SystemConfigModel(key={self.key})>"


class OutboxEventModel(Base):
    """Outbox table for reliable event publishing."""

    __tablename__ = "outbox_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    aggregate_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Processing status
    status: Mapped[str] = mapped_column(
        String(20), 
        default="pending", 
        index=True
    )  # pending, processing, completed, failed, dead_letter
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Partition info for time-series partitioning
    partition_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, index=True)

    __table_args__ = (
        Index("ix_outbox_status_created", "status", "created_at"),
        Index("ix_outbox_aggregate", "aggregate_type", "aggregate_id"),
    )

    def __repr__(self):
        return f"<OutboxEventModel(id={self.id}, type={self.event_type}, status={self.status})>"


class RuntimeMetricModel(Base):
    """Runtime metrics storage for monitoring."""

    __tablename__ = "runtime_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False)  # gauge, counter, histogram
    
    # Metric value
    value: Mapped[float] = mapped_column(nullable=False)
    
    # Labels for filtering
    labels: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Timestamps
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_metrics_name_timestamp", "metric_name", "timestamp"),
    )

    def __repr__(self):
        return f"<RuntimeMetricModel(name={self.metric_name}, value={self.value})>"