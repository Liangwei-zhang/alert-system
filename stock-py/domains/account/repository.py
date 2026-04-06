from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.models.account import UserAccountModel
from infra.db.models.auth import UserModel
from infra.db.models.portfolio import PortfolioPositionModel
from infra.db.models.watchlist import WatchlistItemModel


class AccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_profile(self, user_id: int) -> tuple[UserModel | None, UserAccountModel | None]:
        user_result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
        account_result = await self.session.execute(
            select(UserAccountModel).where(UserAccountModel.user_id == user_id)
        )
        return user_result.scalar_one_or_none(), account_result.scalar_one_or_none()

    async def get_dashboard(self, user_id: int) -> dict:
        user, account = await self.get_profile(user_id)
        watchlist_result = await self.session.execute(
            select(WatchlistItemModel)
            .where(WatchlistItemModel.user_id == user_id)
            .order_by(WatchlistItemModel.created_at.desc())
        )
        portfolio_result = await self.session.execute(
            select(PortfolioPositionModel)
            .where(PortfolioPositionModel.user_id == user_id)
            .order_by(PortfolioPositionModel.total_capital.desc())
        )

        return {
            "user": user,
            "account": account,
            "watchlist": list(watchlist_result.scalars().all()),
            "portfolio": list(portfolio_result.scalars().all()),
        }

    async def upsert_account(
        self,
        user_id: int,
        total_capital: float | None = None,
        currency: str | None = None,
    ) -> None:
        stmt = insert(UserAccountModel).values(
            user_id=user_id,
            total_capital=total_capital if total_capital is not None else 0,
            currency=currency or "USD",
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[UserAccountModel.user_id],
            set_={
                "total_capital": (
                    total_capital if total_capital is not None else UserAccountModel.total_capital
                ),
                "currency": currency if currency is not None else UserAccountModel.currency,
            },
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def update_user_profile(
        self,
        user_id: int,
        name: str | None = None,
        locale: str | None = None,
        timezone_name: str | None = None,
    ) -> None:
        user = await self.session.get(UserModel, user_id)
        if user is None:
            return
        if name is not None:
            user.name = name
        if locale is not None:
            user.locale = locale
        if timezone_name is not None:
            user.timezone = timezone_name
        await self.session.flush()
