"""
Subscription service for subscription business logic.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from domains.subscription.subscription import Subscription, SubscriptionTier, SubscriptionStatus
from domains.auth.user import User


class SubscriptionService:
    """Service for subscription management."""

    def __init__(self, db: Session):
        self.db = db

    # ============== CRUD Operations ==============

    def get_by_id(self, subscription_id: int) -> Optional[Subscription]:
        """Get subscription by ID."""
        return self.db.execute(
            select(Subscription).where(Subscription.id == subscription_id)
        ).scalar_one_or_none()

    def get_by_user_id(self, user_id: int) -> Optional[Subscription]:
        """Get subscription by user ID."""
        return self.db.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        ).scalar_one_or_none()

    def list_subscriptions(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[SubscriptionStatus] = None,
        tier: Optional[SubscriptionTier] = None,
        include_expired: bool = False,
    ) -> List[Subscription]:
        """List subscriptions with optional filters."""
        query = select(Subscription)
        if status:
            query = query.where(Subscription.status == status)
        if tier:
            query = query.where(Subscription.tier == tier)
        if not include_expired:
            # Exclude expired by default
            query = query.where(Subscription.status != SubscriptionStatus.EXPIRED)
        
        return list(
            self.db.execute(
                query.offset(skip).limit(limit).order_by(Subscription.created_at.desc())
            ).scalars().all()
        )

    def create_subscription(
        self,
        user_id: int,
        tier: SubscriptionTier = SubscriptionTier.FREE,
        is_trial: bool = False,
        trial_days: int = 14,
    ) -> Subscription:
        """Create a new subscription for a user."""
        # Check if user already has a subscription
        existing = self.get_by_user_id(user_id)
        if existing:
            raise ValueError(f"User {user_id} already has a subscription")

        # Get tier features
        tier_features = self._get_tier_features(tier)

        now = datetime.utcnow()
        trial_ends = now + timedelta(days=trial_days) if is_trial else None

        subscription = Subscription(
            user_id=user_id,
            tier=tier,
            status=SubscriptionStatus.TRIAL if is_trial else SubscriptionStatus.ACTIVE,
            signals_per_day=tier_features["signals_per_day"],
            max_portfolios=tier_features["max_portfolios"],
            max_strategies=tier_features["max_strategies"],
            realtime_signals=tier_features["realtime_signals"],
            backtesting=tier_features["backtesting"],
            api_access=tier_features["api_access"],
            is_trial=is_trial,
            trial_ends_at=trial_ends,
            current_period_start=now,
            current_period_end=trial_ends,
        )
        self.db.add(subscription)
        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def update_subscription(
        self,
        subscription_id: int,
        tier: Optional[SubscriptionTier] = None,
        status: Optional[SubscriptionStatus] = None,
        signals_per_day: Optional[int] = None,
        max_portfolios: Optional[int] = None,
        max_strategies: Optional[int] = None,
        realtime_signals: Optional[bool] = None,
        backtesting: Optional[bool] = None,
        api_access: Optional[bool] = None,
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None,
    ) -> Optional[Subscription]:
        """Update subscription details."""
        sub = self.get_by_id(subscription_id)
        if not sub:
            return None

        if tier is not None:
            # Update tier and features
            sub.tier = tier
            tier_features = self._get_tier_features(tier)
            sub.signals_per_day = tier_features["signals_per_day"]
            sub.max_portfolios = tier_features["max_portfolios"]
            sub.max_strategies = tier_features["max_strategies"]
            sub.realtime_signals = tier_features["realtime_signals"]
            sub.backtesting = tier_features["backtesting"]
            sub.api_access = tier_features["api_access"]

        if status is not None:
            sub.status = status
            if status == SubscriptionStatus.CANCELLED:
                sub.cancelled_at = datetime.utcnow()
            elif status == SubscriptionStatus.ACTIVE:
                sub.cancelled_at = None

        if signals_per_day is not None:
            sub.signals_per_day = signals_per_day
        if max_portfolios is not None:
            sub.max_portfolios = max_portfolios
        if max_strategies is not None:
            sub.max_strategies = max_strategies
        if realtime_signals is not None:
            sub.realtime_signals = realtime_signals
        if backtesting is not None:
            sub.backtesting = backtesting
        if api_access is not None:
            sub.api_access = api_access
        if stripe_customer_id is not None:
            sub.stripe_customer_id = stripe_customer_id
        if stripe_subscription_id is not None:
            sub.stripe_subscription_id = stripe_subscription_id

        sub.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def delete_subscription(self, subscription_id: int) -> bool:
        """Delete a subscription (soft delete via status)."""
        sub = self.get_by_id(subscription_id)
        if not sub:
            return False
        
        sub.status = SubscriptionStatus.CANCELLED
        sub.cancelled_at = datetime.utcnow()
        sub.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    # ============== Status Management ==============

    def pause_subscription(self, subscription_id: int) -> Optional[Subscription]:
        """Pause an active subscription."""
        sub = self.get_by_id(subscription_id)
        if not sub or sub.status != SubscriptionStatus.ACTIVE:
            return None
        
        sub.status = SubscriptionStatus.CANCELLED  # Or a PAUSED status if added
        sub.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def resume_subscription(self, subscription_id: int) -> Optional[Subscription]:
        """Resume a paused subscription."""
        sub = self.get_by_id(subscription_id)
        if not sub or sub.status != SubscriptionStatus.CANCELLED:
            return None
        
        sub.status = SubscriptionStatus.ACTIVE
        sub.cancelled_at = None
        sub.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def expire_subscription(self, subscription_id: int) -> Optional[Subscription]:
        """Manually expire a subscription."""
        sub = self.get_by_id(subscription_id)
        if not sub:
            return None
        
        sub.status = SubscriptionStatus.EXPIRED
        sub.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def reactivate_subscription(self, subscription_id: int) -> Optional[Subscription]:
        """Reactivate an expired or cancelled subscription."""
        sub = self.get_by_id(subscription_id)
        if not sub:
            return None
        
        sub.status = SubscriptionStatus.ACTIVE
        sub.cancelled_at = None
        sub.current_period_start = datetime.utcnow()
        sub.current_period_end = datetime.utcnow() + timedelta(days=30)
        sub.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(sub)
        return sub

    # ============== Renewal Handling ==============

    def handle_renewal(
        self,
        subscription_id: int,
        new_period_end: datetime,
    ) -> Optional[Subscription]:
        """Handle subscription renewal."""
        sub = self.get_by_id(subscription_id)
        if not sub:
            return None

        # Check if auto-renew is disabled (cancelled or expired)
        if sub.status in [SubscriptionStatus.CANCELLED, SubscriptionStatus.EXPIRED]:
            return None

        # Extend the current period
        sub.current_period_start = sub.current_period_end or datetime.utcnow()
        sub.current_period_end = new_period_end
        sub.updated_at = datetime.utcnow()

        # If was on trial, convert to active
        if sub.status == SubscriptionStatus.TRIAL:
            sub.status = SubscriptionStatus.ACTIVE
            sub.is_trial = False
            sub.trial_ends_at = None

        self.db.commit()
        self.db.refresh(sub)
        return sub

    def check_and_process_expired(self) -> List[Subscription]:
        """Check for expired subscriptions and process them."""
        now = datetime.utcnow()
        expired_subs = list(
            self.db.execute(
                select(Subscription).where(
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.current_period_end < now,
                )
            ).scalars().all()
        )

        for sub in expired_subs:
            sub.status = SubscriptionStatus.EXPIRED
            sub.updated_at = now
            self.db.commit()
            self.db.refresh(sub)

        return expired_subs

    def check_trials_expiring(self, days: int = 3) -> List[Subscription]:
        """Check trials expiring within specified days."""
        from datetime import timedelta
        now = datetime.utcnow()
        threshold = now + timedelta(days=days)

        return list(
            self.db.execute(
                select(Subscription).where(
                    Subscription.is_trial == True,
                    Subscription.status == SubscriptionStatus.TRIAL,
                    Subscription.trial_ends_at <= threshold,
                    Subscription.trial_ends_at > now,
                )
            ).scalars().all()
        )

    # ============== Stats ==============

    def get_stats(self) -> Dict[str, Any]:
        """Get subscription statistics."""
        total = self.db.execute(select(func.count(Subscription.id))).scalar()
        active = self.db.execute(
            select(func.count(Subscription.id)).where(
                Subscription.status == SubscriptionStatus.ACTIVE
            )
        ).scalar()
        trial = self.db.execute(
            select(func.count(Subscription.id)).where(
                Subscription.is_trial == True
            )
        ).scalar()
        past_due = self.db.execute(
            select(func.count(Subscription.id)).where(
                Subscription.status == SubscriptionStatus.PAST_DUE
            )
        ).scalar()
        expired = self.db.execute(
            select(func.count(Subscription.id)).where(
                Subscription.status == SubscriptionStatus.EXPIRED
            )
        ).scalar()
        cancelled = self.db.execute(
            select(func.count(Subscription.id)).where(
                Subscription.status == SubscriptionStatus.CANCELLED
            )
        ).scalar()

        # Tier breakdown
        tier_counts = {}
        for tier in SubscriptionTier:
            tier_counts[tier.value] = self.db.execute(
                select(func.count(Subscription.id)).where(
                    Subscription.tier == tier
                )
            ).scalar()

        return {
            "total": total,
            "active": active,
            "trial": trial,
            "past_due": past_due,
            "expired": expired,
            "cancelled": cancelled,
            "by_tier": tier_counts,
        }

    # ============== Helpers ==============

    def _get_tier_features(self, tier: SubscriptionTier) -> Dict[str, Any]:
        """Get features for a subscription tier."""
        features = {
            SubscriptionTier.FREE: {
                "signals_per_day": 5,
                "max_portfolios": 1,
                "max_strategies": 1,
                "realtime_signals": False,
                "backtesting": False,
                "api_access": False,
            },
            SubscriptionTier.BASIC: {
                "signals_per_day": 20,
                "max_portfolios": 3,
                "max_strategies": 5,
                "realtime_signals": False,
                "backtesting": False,
                "api_access": False,
            },
            SubscriptionTier.PRO: {
                "signals_per_day": 100,
                "max_portfolios": 10,
                "max_strategies": 20,
                "realtime_signals": True,
                "backtesting": True,
                "api_access": False,
            },
            SubscriptionTier.ENTERPRISE: {
                "signals_per_day": -1,  # Unlimited
                "max_portfolios": -1,
                "max_strategies": -1,
                "realtime_signals": True,
                "backtesting": True,
                "api_access": True,
            },
        }
        return features.get(tier, features[SubscriptionTier.FREE])

    def can_user_access_feature(self, user_id: int, feature: str) -> bool:
        """Check if user has access to a specific feature."""
        sub = self.get_by_user_id(user_id)
        if not sub or sub.status != SubscriptionStatus.ACTIVE:
            return False

        feature_map = {
            "realtime_signals": sub.realtime_signals,
            "backtesting": sub.backtesting,
            "api_access": sub.api_access,
            "unlimited_signals": sub.signals_per_day == -1,
            "unlimited_portfolios": sub.max_portfolios == -1,
            "unlimited_strategies": sub.max_strategies == -1,
        }
        return feature_map.get(feature, False)