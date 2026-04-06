from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.models.account import SubscriptionSnapshotModel
from infra.db.models.auth import UserModel
from infra.db.models.portfolio import PortfolioPositionModel
from infra.db.models.watchlist import WatchlistItemModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_snapshot(
        self, user_id: int, snapshot: dict[str, Any]
    ) -> SubscriptionSnapshotModel:
        model = SubscriptionSnapshotModel(user_id=user_id, snapshot=snapshot)
        self.session.add(model)
        await self.session.flush()
        return model

    async def update_user_subscription_extra(self, user_id: int, extra: dict[str, Any]) -> None:
        user = await self.session.get(UserModel, user_id)
        if user is None:
            return
        user.extra = extra
        await self.session.flush()

    async def load_subscription_summary(self, user_id: int) -> dict[str, int]:
        watchlist_count_result = await self.session.execute(
            select(func.count(WatchlistItemModel.id)).where(WatchlistItemModel.user_id == user_id)
        )
        watchlist_notify_result = await self.session.execute(
            select(func.count(WatchlistItemModel.id)).where(
                WatchlistItemModel.user_id == user_id,
                WatchlistItemModel.notify.is_(True),
            )
        )
        portfolio_count_result = await self.session.execute(
            select(func.count(PortfolioPositionModel.id)).where(
                PortfolioPositionModel.user_id == user_id
            )
        )
        return {
            "watchlist_count": int(watchlist_count_result.scalar_one() or 0),
            "watchlist_notify_enabled": int(watchlist_notify_result.scalar_one() or 0),
            "portfolio_count": int(portfolio_count_result.scalar_one() or 0),
            "push_device_count": 0,
        }
