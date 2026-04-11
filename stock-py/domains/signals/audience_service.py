from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import distinct, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.models.portfolio import PortfolioPositionModel
from infra.db.models.watchlist import WatchlistItemModel

DEFAULT_AUDIENCE_BATCH_SIZE = 1000


class SignalAudienceResolver:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve_recipient_ids(self, symbol: str, score: float) -> list[int]:
        user_ids: list[int] = []
        async for chunk in self.iter_recipient_batches(symbol, score, batch_size=5000):
            user_ids.extend(chunk)
        return user_ids

    async def iter_recipient_batches(
        self,
        symbol: str,
        score: float,
        *,
        batch_size: int = DEFAULT_AUDIENCE_BATCH_SIZE,
        after_user_id: int = 0,
    ) -> AsyncIterator[list[int]]:
        normalized_symbol = symbol.upper()
        min_score = int(score)
        cursor = max(int(after_user_id), 0)
        normalized_batch_size = max(int(batch_size), 1)

        while True:
            user_ids = await self._fetch_recipient_chunk(
                symbol=normalized_symbol,
                min_score=min_score,
                after_user_id=cursor,
                limit=normalized_batch_size,
            )
            if not user_ids:
                return

            yield user_ids
            cursor = user_ids[-1]

    async def _fetch_recipient_chunk(
        self,
        *,
        symbol: str,
        min_score: int,
        after_user_id: int,
        limit: int,
    ) -> list[int]:
        watchlist_query = select(WatchlistItemModel.user_id.label("user_id")).where(
            WatchlistItemModel.symbol == symbol,
            WatchlistItemModel.notify.is_(True),
            WatchlistItemModel.min_score <= min_score,
        )
        portfolio_query = select(PortfolioPositionModel.user_id.label("user_id")).where(
            PortfolioPositionModel.symbol == symbol,
            PortfolioPositionModel.notify.is_(True),
        )
        recipients_union = union_all(watchlist_query, portfolio_query).subquery()

        result = await self.session.execute(
            select(distinct(recipients_union.c.user_id))
            .where(recipients_union.c.user_id > after_user_id)
            .order_by(recipients_union.c.user_id.asc())
            .limit(limit)
        )
        return [int(user_id) for user_id in result.scalars().all()]

    async def resolve_recipients_count(self, symbol: str, score: float) -> int:
        normalized_symbol = symbol.upper()
        min_score = int(score)
        watchlist_result = await self.session.execute(
            select(WatchlistItemModel.user_id).where(
                WatchlistItemModel.symbol == normalized_symbol,
                WatchlistItemModel.notify.is_(True),
                WatchlistItemModel.min_score <= min_score,
            )
        )
        portfolio_result = await self.session.execute(
            select(PortfolioPositionModel.user_id).where(
                PortfolioPositionModel.symbol == normalized_symbol,
                PortfolioPositionModel.notify.is_(True),
            )
        )
        user_ids = set(watchlist_result.scalars().all()) | set(portfolio_result.scalars().all())
        return len(user_ids)
