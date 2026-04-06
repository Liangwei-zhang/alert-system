from __future__ import annotations

from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infra.cache.account_dashboard_cache import (
    apply_account_dashboard_cache_operations,
    pop_pending_account_dashboard_cache_operations,
)
from infra.cache.account_profile_cache import (
    apply_account_profile_cache_operations,
    pop_pending_account_profile_cache_operations,
)
from infra.cache.push_devices_cache import (
    apply_push_devices_cache_operations,
    pop_pending_push_devices_cache_operations,
)
from infra.cache.trade_info_cache import (
    apply_trade_info_cache_operations,
    pop_pending_trade_info_cache_operations,
)
from infra.db.session import get_session_factory
from infra.security.session_cache import (
    apply_session_cache_operations,
    pop_pending_session_cache_operations,
)


class AsyncUnitOfWork:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._session_factory = session_factory or get_session_factory()
        self.session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> Self:
        self.session = self._session_factory()
        self._committed = False
        return self

    async def __aexit__(self, exc_type, exc, _tb) -> None:
        if self.session is None:
            return

        try:
            if exc_type is not None or not self._committed:
                await self.rollback()
        finally:
            await self.session.close()
            self.session = None

    async def commit(self) -> None:
        if self.session is None:
            raise RuntimeError("Unit of work has not been entered")

        await self.session.commit()
        await apply_session_cache_operations(pop_pending_session_cache_operations(self.session))
        await apply_account_dashboard_cache_operations(
            pop_pending_account_dashboard_cache_operations(self.session)
        )
        await apply_account_profile_cache_operations(
            pop_pending_account_profile_cache_operations(self.session)
        )
        await apply_push_devices_cache_operations(
            pop_pending_push_devices_cache_operations(self.session)
        )
        await apply_trade_info_cache_operations(
            pop_pending_trade_info_cache_operations(self.session)
        )
        self._committed = True

    async def rollback(self) -> None:
        if self.session is None:
            return

        pop_pending_session_cache_operations(self.session)
        pop_pending_account_dashboard_cache_operations(self.session)
        pop_pending_account_profile_cache_operations(self.session)
        pop_pending_push_devices_cache_operations(self.session)
        pop_pending_trade_info_cache_operations(self.session)
        await self.session.rollback()

    async def flush(self) -> None:
        if self.session is None:
            raise RuntimeError("Unit of work has not been entered")
        await self.session.flush()
