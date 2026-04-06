"""
Basic admin service for user management and system stats.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from domains.admin.admin import AdminUser, AdminRole
from domains.auth.user import User
from domains.signals.signal import Signal, SignalStatus
from domains.subscription.subscription import Subscription, SubscriptionTier, SubscriptionStatus
from domains.search.stock import Stock
from domains.portfolio.portfolio import Portfolio
from domains.tradingagents.strategy import Strategy


class AdminService:
    """Service for admin user management."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> Optional[AdminUser]:
        """Get admin user by ID."""
        return self.db.execute(
            select(AdminUser).where(AdminUser.id == user_id)
        ).scalar_one_or_none()

    def get_by_username(self, username: str) -> Optional[AdminUser]:
        """Get admin user by username."""
        return self.db.execute(
            select(AdminUser).where(AdminUser.username == username)
        ).scalar_one_or_none()

    def get_by_email(self, email: str) -> Optional[AdminUser]:
        """Get admin user by email."""
        return self.db.execute(
            select(AdminUser).where(AdminUser.email == email)
        ).scalar_one_or_none()

    def list_users(self, skip: int = 0, limit: int = 100) -> List[AdminUser]:
        """List all admin users."""
        return list(
            self.db.execute(
                select(AdminUser).offset(skip).limit(limit)
            ).scalars().all()
        )

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        role: AdminRole = AdminRole.VIEWER,
    ) -> AdminUser:
        """Create a new admin user."""
        # TODO: Implement password hashing
        user = AdminUser(
            username=username,
            email=email,
            hashed_password=password,  # Hash in production
            full_name=full_name,
            role=role,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_user(
        self,
        user_id: int,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
        role: Optional[AdminRole] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[AdminUser]:
        """Update an admin user."""
        user = self.get_by_id(user_id)
        if not user:
            return None

        if email is not None:
            user.email = email
        if full_name is not None:
            user.full_name = full_name
        if role is not None:
            user.role = role
        if is_active is not None:
            user.is_active = is_active

        user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(self, user_id: int) -> bool:
        """Delete an admin user."""
        user = self.get_by_id(user_id)
        if not user:
            return False
        self.db.delete(user)
        self.db.commit()
        return True

    def update_last_login(self, user_id: int) -> None:
        """Update last login timestamp."""
        user = self.get_by_id(user_id)
        if user:
            user.last_login = datetime.utcnow()
            self.db.commit()

    # ============== System Stats ==============

    def get_system_stats(self) -> Dict[str, Any]:
        """Get system-wide statistics."""
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        last_30d = now - timedelta(days=30)

        # User stats
        total_users = self.db.execute(select(func.count(User.id))).scalar()
        active_users = self.db.execute(
            select(func.count(User.id)).where(User.is_active == True)
        ).scalar()
        new_users_24h = self.db.execute(
            select(func.count(User.id)).where(User.created_at >= last_24h)
        ).scalar()
        new_users_7d = self.db.execute(
            select(func.count(User.id)).where(User.created_at >= last_7d)
        ).scalar()

        # Signal stats
        total_signals = self.db.execute(select(func.count(Signal.id))).scalar()
        active_signals = self.db.execute(
            select(func.count(Signal.id)).where(Signal.status == SignalStatus.ACTIVE)
        ).scalar()
        triggered_signals = self.db.execute(
            select(func.count(Signal.id)).where(Signal.status == SignalStatus.TRIGGERED)
        ).scalar()
        signals_24h = self.db.execute(
            select(func.count(Signal.id)).where(Signal.generated_at >= last_24h)
        ).scalar()

        # Stock stats
        total_stocks = self.db.execute(select(func.count(Stock.id))).scalar()
        active_stocks = self.db.execute(
            select(func.count(Stock.id)).where(Stock.is_active == True)
        ).scalar()

        # Portfolio stats
        total_portfolios = self.db.execute(select(func.count(Portfolio.id))).scalar()

        # Strategy stats
        total_strategies = self.db.execute(select(func.count(Strategy.id))).scalar()

        return {
            "users": {
                "total": total_users,
                "active": active_users,
                "new_24h": new_users_24h,
                "new_7d": new_users_7d,
            },
            "signals": {
                "total": total_signals,
                "active": active_signals,
                "triggered": triggered_signals,
                "generated_24h": signals_24h,
            },
            "stocks": {
                "total": total_stocks,
                "active": active_stocks,
            },
            "portfolios": {
                "total": total_portfolios,
            },
            "strategies": {
                "total": total_strategies,
            },
            "timestamp": now.isoformat(),
        }

    def get_subscription_stats(self) -> Dict[str, Any]:
        """Get subscription statistics."""
        total_subs = self.db.execute(select(func.count(Subscription.id))).scalar()
        active_subs = self.db.execute(
            select(func.count(Subscription.id)).where(
                Subscription.status == SubscriptionStatus.ACTIVE
            )
        ).scalar()
        trial_subs = self.db.execute(
            select(func.count(Subscription.id)).where(
                Subscription.is_trial == True
            )
        ).scalar()
        past_due = self.db.execute(
            select(func.count(Subscription.id)).where(
                Subscription.status == SubscriptionStatus.PAST_DUE
            )
        ).scalar()

        # Tier breakdown
        tier_counts = {}
        for tier in SubscriptionTier:
            count = self.db.execute(
                select(func.count(Subscription.id)).where(
                    Subscription.tier == tier
                )
            ).scalar()
            tier_counts[tier.value] = count

        return {
            "total": total_subs,
            "active": active_subs,
            "trial": trial_subs,
            "past_due": past_due,
            "by_tier": tier_counts,
        }

    def list_subscriptions(
        self, 
        skip: int = 0, 
        limit: int = 100,
        status: Optional[SubscriptionStatus] = None,
        tier: Optional[SubscriptionTier] = None,
    ) -> List[Subscription]:
        """List subscriptions with optional filters."""
        query = select(Subscription)
        if status:
            query = query.where(Subscription.status == status)
        if tier:
            query = query.where(Subscription.tier == tier)
        
        return list(
            self.db.execute(
                query.offset(skip).limit(limit).order_by(Subscription.created_at.desc())
            ).scalars().all()
        )

    def get_subscription_by_id(self, subscription_id: int) -> Optional[Subscription]:
        """Get subscription by ID."""
        return self.db.execute(
            select(Subscription).where(Subscription.id == subscription_id)
        ).scalar_one_or_none()

    def get_subscription_by_user_id(self, user_id: int) -> Optional[Subscription]:
        """Get subscription by user ID."""
        return self.db.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        ).scalar_one_or_none()

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
    ) -> Optional[Subscription]:
        """Update subscription."""
        sub = self.get_subscription_by_id(subscription_id)
        if not sub:
            return None

        if tier is not None:
            sub.tier = tier
        if status is not None:
            sub.status = status
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

        sub.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(sub)
        return sub