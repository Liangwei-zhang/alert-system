"""Unit of Work pattern for database transactions."""
from typing import Any, Optional
from abc import ABC, abstractmethod


class AsyncUnitOfWork(ABC):
    """Abstract async unit of work."""
    
    @abstractmethod
    async def commit(self) -> None:
        """Commit the current transaction."""
        pass
    
    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the current transaction."""
        pass
    
    @abstractmethod
    async def flush(self) -> None:
        """Flush pending changes to the database."""
        pass
    
    @abstractmethod
    async def __aenter__(self) -> "AsyncUnitOfWork":
        pass
    
    @abstractmethod
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass


class SQLAlchemyUnitOfWork(AsyncUnitOfWork):
    """SQLAlchemy implementation of AsyncUnitOfWork."""
    
    def __init__(self, session: Any):
        self._session = session
    
    @property
    def session(self) -> Any:
        return self._session
    
    async def commit(self) -> None:
        await self._session.commit()
    
    async def rollback(self) -> None:
        await self._session.rollback()
    
    async def flush(self) -> None:
        await self._session.flush()
    
    async def __aenter__(self) -> "SQLAlchemyUnitOfWork":
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            await self.rollback()
        await self._session.close()