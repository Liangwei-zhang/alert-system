from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.models.symbols import SymbolModel
from infra.db.models.watchlist import WatchlistItemModel


class WatchlistRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_user(self, user_id: int) -> list[WatchlistItemModel]:
        result = await self.session.execute(
            select(WatchlistItemModel)
            .where(WatchlistItemModel.user_id == user_id)
            .order_by(WatchlistItemModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, item_id: int) -> WatchlistItemModel | None:
        result = await self.session.execute(
            select(WatchlistItemModel).where(WatchlistItemModel.id == item_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_and_symbol(self, user_id: int, symbol: str) -> WatchlistItemModel | None:
        result = await self.session.execute(
            select(WatchlistItemModel).where(
                WatchlistItemModel.user_id == user_id,
                WatchlistItemModel.symbol == symbol,
            )
        )
        return result.scalar_one_or_none()

    async def ensure_symbol_exists(self, symbol: str) -> None:
        stmt = insert(SymbolModel).values(symbol=symbol, name=symbol)
        stmt = stmt.on_conflict_do_nothing(index_elements=[SymbolModel.symbol])
        await self.session.execute(stmt)
        await self.session.flush()

    async def create(
        self, user_id: int, symbol: str, notify: bool, min_score: int
    ) -> WatchlistItemModel:
        await self.ensure_symbol_exists(symbol)
        stmt = insert(WatchlistItemModel).values(
            user_id=user_id,
            symbol=symbol,
            notify=notify,
            min_score=min_score,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[WatchlistItemModel.user_id, WatchlistItemModel.symbol],
            set_={"notify": notify, "min_score": min_score},
        )
        await self.session.execute(stmt)
        await self.session.flush()
        item = await self.get_by_user_and_symbol(user_id, symbol)
        if item is None:
            raise RuntimeError("Failed to create watchlist item")
        return item

    async def update(
        self,
        item: WatchlistItemModel,
        notify: bool | None = None,
        min_score: int | None = None,
    ) -> WatchlistItemModel:
        if notify is not None:
            item.notify = notify
        if min_score is not None:
            item.min_score = min_score
        await self.session.flush()
        return item

    async def delete(self, item: WatchlistItemModel) -> None:
        await self.session.delete(item)
        await self.session.flush()

    async def replace_all(self, user_id: int, items: list[dict]) -> None:
        symbols = [str(item["symbol"]) for item in items]
        for symbol in symbols:
            await self.ensure_symbol_exists(symbol)

        if symbols:
            await self.session.execute(
                delete(WatchlistItemModel).where(
                    WatchlistItemModel.user_id == user_id,
                    WatchlistItemModel.symbol.not_in(symbols),
                )
            )
        else:
            await self.session.execute(
                delete(WatchlistItemModel).where(WatchlistItemModel.user_id == user_id)
            )

        for item in items:
            await self.create(
                user_id=user_id,
                symbol=str(item["symbol"]),
                notify=bool(item.get("notify", True)),
                min_score=int(item.get("min_score", 65)),
            )

        await self.session.flush()
