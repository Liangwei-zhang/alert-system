"""
Subscription model for user subscriptions.
"""
from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, Integer, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from infra.database import Base


class SubscriptionTier(str, Enum):
    """Subscription tier levels."""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    """Subscription status."""
    ACTIVE = "active"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"
    TRIAL = "trial"
    EXPIRED = "expired"


class Subscription(Base):
    """User subscription model."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True, unique=True)
    
    # Subscription details
    tier: Mapped[SubscriptionTier] = mapped_column(
        SQLEnum(SubscriptionTier), 
        default=SubscriptionTier.FREE
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        SQLEnum(SubscriptionStatus),
        default=SubscriptionStatus.ACTIVE
    )
    
    # Features
    signals_per_day: Mapped[int] = mapped_column(Integer, default=5)
    max_portfolios: Mapped[int] = mapped_column(Integer, default=1)
    max_strategies: Mapped[int] = mapped_column(Integer, default=1)
    realtime_signals: Mapped[bool] = mapped_column(Boolean, default=False)
    backtesting: Mapped[bool] = mapped_column(Boolean, default=False)
    api_access: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Billing
    stripe_customer_id: Mapped[str] = mapped_column(String(100), nullable=True)
    stripe_subscription_id: Mapped[str] = mapped_column(String(100), nullable=True)
    
    # Trial
    is_trial: Mapped[bool] = mapped_column(Boolean, default=False)
    trial_ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Current period
    current_period_start: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    current_period_end: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Cancellation
    cancelled_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )