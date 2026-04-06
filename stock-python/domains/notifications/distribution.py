"""
Distribution models - message queue, delivery receipts, and archiving.
"""
from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, Integer, ForeignKey, Boolean, Text, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infra.database import Base


class DistributionStatus(str, Enum):
    """Message distribution status."""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    FAILED = "failed"
    ESCALATED = "escalated"
    ARCHIVED = "archived"


class DistributionPriority(str, Enum):
    """Distribution priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class DeliveryReceiptStatus(str, Enum):
    """Delivery receipt status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    BOUNCED = "bounced"


class MessageQueue(Base):
    """Message queue for distribution."""

    __tablename__ = "message_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Message reference
    notification_id: Mapped[int] = mapped_column(Integer, ForeignKey("notifications.id"), nullable=True, index=True)
    
    # Recipient
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    
    # Delivery channel
    channel: Mapped[str] = mapped_column(String(20), default="in_app")  # "in_app", "email", "push", "sms", "webhook"
    
    # Priority and status
    priority: Mapped[DistributionPriority] = mapped_column(
        SQLEnum(DistributionPriority), 
        default=DistributionPriority.NORMAL,
        index=True
    )
    status: Mapped[DistributionStatus] = mapped_column(
        SQLEnum(DistributionStatus),
        default=DistributionStatus.PENDING,
        index=True
    )
    
    # Message content
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    extra_data: Mapped[str] = mapped_column(Text, nullable=True)  # JSON
    
    # Retry tracking
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    last_retry_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Timing
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, index=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Error tracking
    error_message: Mapped[str] = mapped_column(String(500), nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Escalation
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    escalated_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    escalation_note: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="message_queue")


class DeliveryReceipt(Base):
    """Delivery receipt for tracking message delivery."""

    __tablename__ = "delivery_receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Reference to message queue
    queue_id: Mapped[int] = mapped_column(Integer, ForeignKey("message_queue.id"), index=True)
    
    # Channel-specific delivery ID (e.g., email message-id, push notification ID)
    channel_delivery_id: Mapped[str] = mapped_column(String(200), nullable=True, index=True)
    
    # Status
    status: Mapped[DeliveryReceiptStatus] = mapped_column(
        SQLEnum(DeliveryReceiptStatus),
        default=DeliveryReceiptStatus.PENDING,
        index=True
    )
    
    # Timestamps
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    read_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    failed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Channel response metadata
    channel_response: Mapped[str] = mapped_column(Text, nullable=True)  # JSON
    
    # Error details
    error_code: Mapped[str] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Read tracking
    read_device: Mapped[str] = mapped_column(String(100), nullable=True)
    read_ip: Mapped[str] = mapped_column(String(45), nullable=True)  # IPv6 max
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    queue: Mapped["MessageQueue"] = relationship("MessageQueue", back_populates="receipts")


class ArchivedMessage(Base):
    """Archived messages for long-term storage."""

    __tablename__ = "archived_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Original queue reference (for lookup)
    original_queue_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)
    original_notification_id: Mapped[int] = mapped_column(Integer, nullable=True)
    
    # User info (denormalized for archive independence)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    
    # Content (denormalized)
    channel: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    
    # Final status
    status: Mapped[DistributionStatus] = mapped_column(SQLEnum(DistributionStatus))
    delivered_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Retry summary
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    final_error: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Receipt summary
    receipt_status: Mapped[DeliveryReceiptStatus] = mapped_column(SQLEnum(DeliveryReceiptStatus))
    
    # Metadata (denormalized)
    extra_data: Mapped[str] = mapped_column(Text, nullable=True)  # JSON
    
    # Archive info
    archived_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    archive_reason: Mapped[str] = mapped_column(String(50))  # "completed", "failed_max_retries", "manual", "scheduled"
    
    # Timestamps
    original_created_at: Mapped[datetime] = mapped_column(DateTime)
    original_updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


# =============================================================================
# Pydantic Schemas
# =============================================================================

from pydantic import BaseModel, ConfigDict
from typing import Optional
import json


class MessageQueueBase(BaseModel):
    """Base message queue schema."""
    user_id: int
    channel: str = "in_app"
    priority: DistributionPriority = DistributionPriority.NORMAL
    title: str
    message: str


class MessageQueueCreate(MessageQueueBase):
    """Message queue creation schema."""
    notification_id: Optional[int] = None
    metadata: Optional[dict] = None
    scheduled_at: Optional[datetime] = None
    max_retries: int = 3


class MessageQueueResponse(MessageQueueBase):
    """Message queue response schema."""
    id: int
    notification_id: Optional[int] = None
    status: DistributionStatus
    retry_count: int
    max_retries: int
    scheduled_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    error_message: Optional[str] = None
    escalation_level: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm(cls, obj):
        """Convert ORM to response."""
        data = {}
        for field in ["id", "notification_id", "user_id", "channel", "priority", "status",
                      "title", "message", "retry_count", "max_retries", "scheduled_at",
                      "processed_at", "delivered_at", "error_message", "escalation_level", "created_at"]:
            data[field] = getattr(obj, field, None)
        return cls(**data)


class DeliveryReceiptResponse(BaseModel):
    """Delivery receipt response schema."""
    id: int
    queue_id: int
    channel_delivery_id: Optional[str] = None
    status: DeliveryReceiptStatus
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArchivedMessageResponse(BaseModel):
    """Archived message response schema."""
    id: int
    original_queue_id: Optional[int] = None
    user_id: int
    channel: str
    title: str
    message: str
    status: DistributionStatus
    delivered_at: Optional[datetime] = None
    receipt_status: DeliveryReceiptStatus
    archived_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QueueStatsResponse(BaseModel):
    """Queue statistics response."""
    pending: int
    processing: int
    delivered: int
    failed: int
    escalated: int
    by_priority: dict


class EscalateRequest(BaseModel):
    """Escalation request schema."""
    queue_id: int
    note: Optional[str] = None


# =============================================================================
# Relationship Back Populates
# =============================================================================

from domains.auth.user import User

User.message_queue = relationship("MessageQueue", back_populates="user", cascade="all, delete-orphan")
MessageQueue.receipts = relationship("DeliveryReceipt", back_populates="queue", cascade="all, delete-orphan")