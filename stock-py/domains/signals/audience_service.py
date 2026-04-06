from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.models.portfolio import PortfolioPositionModel
from infra.db.models.watchlist import WatchlistItemModel


class SignalAudienceResolver:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve_recipient_ids(self, symbol: str, score: float) -> list[int]:
        normalized_symbol = symbol.upper()
        watchlist_result = await self.session.execute(
            select(WatchlistItemModel.user_id).where(
                WatchlistItemModel.symbol == normalized_symbol,
                WatchlistItemModel.notify.is_(True),
                WatchlistItemModel.min_score <= int(score),
            )
        )
        portfolio_result = await self.session.execute(
            select(PortfolioPositionModel.user_id).where(
                PortfolioPositionModel.symbol == normalized_symbol,
                PortfolioPositionModel.notify.is_(True),
            )
        )
        user_ids = set(watchlist_result.scalars().all()) | set(portfolio_result.scalars().all())
        return sorted(int(user_id) for user_id in user_ids)
