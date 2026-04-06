from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.models.symbols import SymbolModel


class SearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search_symbols(
        self, q: str, limit: int = 20, asset_type: str | None = None
    ) -> list[SymbolModel]:
        symbol_like = f"{q}%"
        fuzzy_like = f"%{q}%"
        stmt = select(SymbolModel).where(
            SymbolModel.is_active.is_(True),
            (
                SymbolModel.symbol.ilike(symbol_like)
                | SymbolModel.name.ilike(fuzzy_like)
                | SymbolModel.name_zh.ilike(fuzzy_like)
            ),
        )
        if asset_type:
            stmt = stmt.where(SymbolModel.asset_type == asset_type)
        stmt = stmt.order_by(SymbolModel.symbol.asc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_symbol_by_code(self, code: str) -> SymbolModel | None:
        result = await self.session.execute(
            select(SymbolModel).where(SymbolModel.symbol == code.upper())
        )
        return result.scalar_one_or_none()
