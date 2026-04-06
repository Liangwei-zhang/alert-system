"""
Notification models - in-app notifications and device registration.
"""
from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, Integer, ForeignKey, Boolean, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infra.database import Base


class NotificationType(str, Enum):
    """Notification type enum."""
    SIGNAL_BUY = "signal_buy"
    SIGNAL_SELL = "signal_sell"
    SIGNAL_SPLIT_BUY = "signal_split_buy"
    SIGNAL_SPLIT_SELL = "signal_split_sell"
    PRICE_ALERT = "price_alert"
    SYSTEM = "system"


class NotificationPriority(str, Enum):
    """Notification priority enum."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class Notification(Base):
    """In-app notification model."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    
    # Notification content
    type: Mapped[NotificationType] = mapped_column(SQLEnum(NotificationType), index=True)
    priority: Mapped[NotificationPriority] = mapped_column(SQLEnum(NotificationPriority), default=NotificationPriority.NORMAL)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    
    # Related entity (optional)
    related_type: Mapped[str] = mapped_column(String(50), nullable=True)  # e.g., "stock", "signal"
    related_id: Mapped[int] = mapped_column(Integer, nullable=True)
    
    # Read status
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Metadata
    extra_data: Mapped[str] = mapped_column(Text, nullable=True)  # JSON string for extra data
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notifications")


class Device(Base):
    """Device model for push notification tokens."""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    
    # Device info
    name: Mapped[str] = mapped_column(String(100), nullable=True)
    platform: Mapped[str] = mapped_column(String(20))  # "ios", "android", "web", "webpush"
    
    # Push token (FCM/APNS)
    push_token: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    push_token_expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # WebPush specific fields
    subscription_endpoint: Mapped[str] = mapped_column(String(500), nullable=True)  # WebPush endpoint
    vapid_public_key: Mapped[str] = mapped_column(String(200), nullable=True)  # P256DH key
    vapid_auth_key: Mapped[str] = mapped_column(String(100), nullable=True)  # Auth secret
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="devices")


# Pydantic schemas for API
from pydantic import BaseModel, ConfigDict
from typing import Optional
import json


class NotificationBase(BaseModel):
    """Base notification schema."""
    type: NotificationType
    title: str
    message: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    related_type: Optional[str] = None
    related_id: Optional[int] = None


class NotificationCreate(NotificationBase):
    """Notification creation schema."""
    metadata: Optional[dict] = None


class NotificationResponse(NotificationBase):
    """Notification response schema."""
    id: int
    user_id: int
    is_read: bool
    read_at: Optional[datetime] = None
    metadata: Optional[dict] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm(cls, obj):
        """Convert ORM object to response schema."""
        data = {}
        for field in ["id", "user_id", "type", "priority", "title", "message",
                      "related_type", "related_id", "is_read", "read_at", "created_at"]:
            value = getattr(obj, field, None)
            if field == "metadata" and value:
                try:
                    value = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    value = None
            data[field] = value
        return cls(**data)


class NotificationListResponse(BaseModel):
    """Paginated notification list response."""
    notifications: list[NotificationResponse]
    total: int
    unread_count: int


class DeviceBase(BaseModel):
    """Base device schema."""
    name: Optional[str] = None
    platform: str


class DeviceCreate(DeviceBase):
    """Device creation schema."""
    push_token: str
    push_token_expires_at: Optional[datetime] = None


class DeviceResponse(DeviceBase):
    """Device response schema."""
    id: int
    user_id: int
    is_active: bool
    last_used_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebPushSubscriptionCreate(BaseModel):
    """WebPush subscription creation schema."""
    endpoint: str
    p256dh: str  # Public key
    auth: str    # Auth secret


class WebPushSubscriptionResponse(BaseModel):
    """WebPush subscription response with VAPID public key."""
    endpoint: str
    p256dh: str
    auth: str
    public_key: str  # Server's VAPID public key for subscription


class MarkReadRequest(BaseModel):
    """Request to mark notifications as read."""
    notification_ids: list[int]


# Import User for relationship back_populates
from domains.auth.user import User

# Add back_populates relationships
User.notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
User.devices = relationship("Device", back_populates="user", cascade="all, delete-orphan")
