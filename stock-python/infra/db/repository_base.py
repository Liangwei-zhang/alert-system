"""Base repository pattern for database operations."""
from typing import Any, Generic, TypeVar, Type, Optional, List
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession


T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """Abstract base repository with common CRUD operations."""
    
    def __init__(self, model: Type[T], session: AsyncSession):
        self._model = model
        self._session = session
    
    @property
    def session(self) -> AsyncSession:
        return self._session
    
    async def add(self, entity: T) -> T:
        """Add an entity to the session."""
        self._session.add(entity)
        await self._session.flush()
        return entity
    
    async def add_many(self, entities: List[T]) -> List[T]:
        """Add multiple entities to the session."""
        self._session.add_all(entities)
        await self._session.flush()
        return entities
    
    async def delete(self, entity: T) -> None:
        """Mark an entity for deletion."""
        await self._session.delete(entity)
        await self._session.flush()
    
    async def flush(self) -> None:
        """Flush pending changes to the database."""
        await self._session.flush()
    
    async def refresh(self, entity: T, *attrs: str) -> None:
        """Refresh an entity from the database."""
        await self._session.refresh(entity, *attrs)
    
    async def get_by_id(self, id: Any) -> Optional[T]:
        """Get an entity by its primary key."""
        return await self._session.get(self._model, id)
    
    async def find_all(self) -> List[T]:
        """Get all entities."""
        from sqlalchemy import select
        result = await self._session.execute(select(self._model))
        return list(result.scalars().all())
    
    async def find_by(self, **filters: Any) -> Optional[T]:
        """Find a single entity by filters."""
        from sqlalchemy import select
        stmt = select(self._model).filter_by(**filters)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def find_many_by(self, **filters: Any) -> List[T]:
        """Find multiple entities by filters."""
        from sqlalchemy import select
        stmt = select(self._model).filter_by(**filters)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())