from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.models.portfolio import PortfolioPositionModel
from infra.db.models.symbols import SymbolModel


class PortfolioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _serialize_extra(extra: dict | str | None) -> str | None:
        if extra is None or isinstance(extra, str):
            return extra
        return json.dumps(extra, default=str)

    async def list_by_user(self, user_id: int) -> list[PortfolioPositionModel]:
        result = await self.session.execute(
            select(PortfolioPositionModel)
            .where(PortfolioPositionModel.user_id == user_id)
            .order_by(PortfolioPositionModel.total_capital.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, item_id: int) -> PortfolioPositionModel | None:
        result = await self.session.execute(
            select(PortfolioPositionModel).where(PortfolioPositionModel.id == item_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_and_symbol(
        self, user_id: int, symbol: str
    ) -> PortfolioPositionModel | None:
        result = await self.session.execute(
            select(PortfolioPositionModel).where(
                PortfolioPositionModel.user_id == user_id,
                PortfolioPositionModel.symbol == symbol,
            )
        )
        return result.scalar_one_or_none()

    async def ensure_symbol_exists(self, symbol: str) -> None:
        stmt = insert(SymbolModel).values(symbol=symbol, name=symbol)
        stmt = stmt.on_conflict_do_nothing(index_elements=[SymbolModel.symbol])
        await self.session.execute(stmt)
        await self.session.flush()

    async def create(
        self,
        user_id: int,
        symbol: str,
        shares: int,
        avg_cost: float,
        target_profit: float,
        stop_loss: float,
        notify: bool,
        notes: str | None,
        extra: dict | str | None = None,
    ) -> PortfolioPositionModel:
        await self.ensure_symbol_exists(symbol)
        total_capital = round(shares * avg_cost, 2)
        serialized_extra = self._serialize_extra(extra)
        stmt = insert(PortfolioPositionModel).values(
            user_id=user_id,
            symbol=symbol,
            shares=shares,
            avg_cost=avg_cost,
            total_capital=total_capital,
            target_profit=target_profit,
            stop_loss=stop_loss,
            notify=notify,
            notes=notes,
            extra=serialized_extra,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[PortfolioPositionModel.user_id, PortfolioPositionModel.symbol],
            set_={
                "shares": shares,
                "avg_cost": avg_cost,
                "total_capital": total_capital,
                "target_profit": target_profit,
                "stop_loss": stop_loss,
                "notify": notify,
                "notes": notes,
                "extra": serialized_extra,
            },
        )
        await self.session.execute(stmt)
        await self.session.flush()
        item = await self.get_by_user_and_symbol(user_id, symbol)
        if item is None:
            raise RuntimeError("Failed to create portfolio item")
        return item

    async def update(self, item: PortfolioPositionModel, updates: dict) -> PortfolioPositionModel:
        for key, value in updates.items():
            if key == "extra":
                value = self._serialize_extra(value)
            setattr(item, key, value)
        if "shares" in updates or "avg_cost" in updates:
            item.total_capital = round(float(item.shares) * float(item.avg_cost), 2)
        await self.session.flush()
        return item

    async def delete(self, item: PortfolioPositionModel) -> None:
        await self.session.delete(item)
        await self.session.flush()

    async def replace_all(self, user_id: int, items: list[dict]) -> None:
        symbols = [str(item["symbol"]) for item in items]
        for symbol in symbols:
            await self.ensure_symbol_exists(symbol)

        if symbols:
            await self.session.execute(
                delete(PortfolioPositionModel).where(
                    PortfolioPositionModel.user_id == user_id,
                    PortfolioPositionModel.symbol.not_in(symbols),
                )
            )
        else:
            await self.session.execute(
                delete(PortfolioPositionModel).where(PortfolioPositionModel.user_id == user_id)
            )

        for item in items:
            await self.create(
                user_id=user_id,
                symbol=str(item["symbol"]),
                shares=int(item["shares"]),
                avg_cost=float(item["avg_cost"]),
                target_profit=float(item.get("target_profit", 0.15)),
                stop_loss=float(item.get("stop_loss", 0.08)),
                notify=bool(item.get("notify", True)),
                notes=item.get("notes"),
                extra=item.get("extra"),
            )

        await self.session.flush()
