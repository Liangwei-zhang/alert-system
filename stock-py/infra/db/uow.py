from __future__ import annotations

from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infra.cache.registry import (
    apply_registered_cache_operations,
    clear_registered_cache_operations,
)
from infra.db.session import get_session_factory


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
        await apply_registered_cache_operations(self.session)
        self._committed = True

    async def rollback(self) -> None:
        if self.session is None:
            return

        clear_registered_cache_operations(self.session)
        await self.session.rollback()

    async def flush(self) -> None:
        if self.session is None:
            raise RuntimeError("Unit of work has not been entered")
        await self.session.flush()
