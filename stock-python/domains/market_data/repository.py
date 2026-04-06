"""
Market data repository - Symbol and OHLCV data access.
"""
from datetime import datetime
from typing import Optional, List, Tuple

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from infra.database import Base
from infra.db.models.market_data import (
    SymbolModel,
    OhlcvModel,
    OhlcvAnomalyModel,
    AssetType,
    SymbolStatus,
    AnomalyType,
)


class SymbolRepository:
    """Repository for Symbol CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, symbol_data: dict) -> SymbolModel:
        """Create a new symbol."""
        symbol = SymbolModel(**symbol_data)
        self.session.add(symbol)
        await self.session.flush()
        await self.session.refresh(symbol)
        return symbol

    async def get_by_id(self, symbol_id: int) -> Optional[SymbolModel]:
        """Get symbol by ID."""
        result = await self.session.execute(
            select(SymbolModel).where(SymbolModel.id == symbol_id)
        )
        return result.scalar_one_or_none()

    async def get_by_symbol(self, symbol: str) -> Optional[SymbolModel]:
        """Get symbol by ticker symbol."""
        result = await self.session.execute(
            select(SymbolModel).where(SymbolModel.symbol == symbol.upper())
        )
        return result.scalar_one_or_none()

    async def search(
        self,
        query: str,
        exchange: Optional[str] = None,
        asset_type: Optional[AssetType] = None,
        limit: int = 20,
    ) -> List[SymbolModel]:
        """Search symbols by name or ticker."""
        conditions = [
            or_(
                SymbolModel.symbol.ilike(f"%{query}%"),
                SymbolModel.name.ilike(f"%{query}%"),
            )
        ]
        
        if exchange:
            conditions.append(SymbolModel.exchange == exchange)
        if asset_type:
            conditions.append(SymbolModel.asset_type == asset_type)
        
        conditions.append(SymbolModel.status == SymbolStatus.ACTIVE)
        
        result = await self.session.execute(
            select(SymbolModel)
            .where(and_(*conditions))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_all(
        self,
        exchange: Optional[str] = None,
        status: Optional[SymbolStatus] = None,
        asset_type: Optional[AssetType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[SymbolModel], int]:
        """Get all symbols with optional filters."""
        conditions = []
        
        if exchange:
            conditions.append(SymbolModel.exchange == exchange)
        if status:
            conditions.append(SymbolModel.status == status)
        if asset_type:
            conditions.append(SymbolModel.asset_type == asset_type)
        
        # Count query
        count_query = select(func.count(SymbolModel.id))
        if conditions:
            count_query = count_query.where(and_(*conditions))
        
        count_result = await self.session.execute(count_query)
        total = count_result.scalar()
        
        # Data query
        data_query = select(SymbolModel)
        if conditions:
            data_query = data_query.where(and_(*conditions))
        data_query = data_query.offset(offset).limit(limit).order_by(SymbolModel.symbol)
        
        result = await self.session.execute(data_query)
        return list(result.scalars().all()), total

    async def update(self, symbol_id: int, update_data: dict) -> Optional[SymbolModel]:
        """Update a symbol."""
        symbol = await self.get_by_id(symbol_id)
        if not symbol:
            return None
        
        for key, value in update_data.items():
            if hasattr(symbol, key):
                setattr(symbol, key, value)
        
        symbol.updated_at = datetime.utcnow()
        await self.session.flush()
        await self.session.refresh(symbol)
        return symbol

    async def delete(self, symbol_id: int) -> bool:
        """Delete a symbol."""
        symbol = await self.get_by_id(symbol_id)
        if not symbol:
            return False
        
        await self.session.delete(symbol)
        await self.session.flush()
        return True

    async def bulk_create(self, symbols_data: List[dict]) -> List[SymbolModel]:
        """Bulk create symbols."""
        symbols = [SymbolModel(**data) for data in symbols_data]
        self.session.add_all(symbols)
        await self.session.flush()
        for symbol in symbols:
            await self.session.refresh(symbol)
        return symbols

    async def upsert(
        self,
        symbol: str,
        data: dict,
    ) -> Tuple[SymbolModel, bool]:
        """Insert or update a symbol. Returns (symbol, is_new)."""
        existing = await self.get_by_symbol(symbol)
        
        if existing:
            for key, value in data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            existing.updated_at = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(existing)
            return existing, False
        else:
            return await self.create({**data, "symbol": symbol.upper()}), True


class OhlcvRepository:
    """Repository for OHLCV CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, ohlcv_data: dict) -> OhlcvModel:
        """Create a new OHLCV record."""
        ohlcv = OhlcvModel(**ohlcv_data)
        self.session.add(ohlcv)
        await self.session.flush()
        await self.session.refresh(ohlcv)
        return ohlcv

    async def get_by_id(self, ohlcv_id: int) -> Optional[OhlcvModel]:
        """Get OHLCV by ID."""
        result = await self.session.execute(
            select(OhlcvModel).where(OhlcvModel.id == ohlcv_id)
        )
        return result.scalar_one_or_none()

    async def get_by_symbol_timeframe(
        self,
        symbol_id: int,
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[OhlcvModel]:
        """Get OHLCV data for a symbol within a date range."""
        conditions = [
            OhlcvModel.symbol_id == symbol_id,
            OhlcvModel.timeframe == timeframe,
        ]
        
        if start_date:
            conditions.append(OhlcvModel.timestamp >= start_date)
        if end_date:
            conditions.append(OhlcvModel.timestamp <= end_date)
        
        result = await self.session.execute(
            select(OhlcvModel)
            .where(and_(*conditions))
            .order_by(OhlcvModel.timestamp.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_latest(
        self,
        symbol_id: int,
        timeframe: str,
    ) -> Optional[OhlcvModel]:
        """Get the most recent OHLCV record for a symbol."""
        result = await self.session.execute(
            select(OhlcvModel)
            .where(
                and_(
                    OhlcvModel.symbol_id == symbol_id,
                    OhlcvModel.timeframe == timeframe,
                )
            )
            .order_by(OhlcvModel.timestamp.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_oldest(
        self,
        symbol_id: int,
        timeframe: str,
    ) -> Optional[OhlcvModel]:
        """Get the oldest OHLCV record for a symbol."""
        result = await self.session.execute(
            select(OhlcvModel)
            .where(
                and_(
                    OhlcvModel.symbol_id == symbol_id,
                    OhlcvModel.timeframe == timeframe,
                )
            )
            .order_by(OhlcvModel.timestamp.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def bulk_create(self, ohlcv_data: List[dict]) -> List[OhlcvModel]:
        """Bulk create OHLCV records."""
        ohlcv_records = [OhlcvModel(**data) for data in ohlcv_data]
        self.session.add_all(ohlcv_records)
        await self.session.flush()
        for ohlcv in ohlcv_records:
            await self.session.refresh(ohlcv)
        return ohlcv_records

    async def bulk_upsert(
        self,
        symbol_id: int,
        timeframe: str,
        data: List[dict],
    ) -> Tuple[int, int]:
        """
        Bulk upsert OHLCV data. Returns (inserted_count, updated_count).
        Uses ON CONFLICT DO UPDATE for PostgreSQL.
        """
        inserted = 0
        updated = 0
        
        for record in data:
            # Check if exists
            existing = await self.session.execute(
                select(OhlcvModel).where(
                    and_(
                        OhlcvModel.symbol_id == symbol_id,
                        OhlcvModel.timestamp == record["timestamp"],
                        OhlcvModel.timeframe == timeframe,
                    )
                )
            )
            existing_obj = existing.scalar_one_or_none()
            
            if existing_obj:
                # Update
                for key, value in record.items():
                    if hasattr(existing_obj, key):
                        setattr(existing_obj, key, value)
                updated += 1
            else:
                # Insert
                record["symbol_id"] = symbol_id
                record["timeframe"] = timeframe
                ohlcv = OhlcvModel(**record)
                self.session.add(ohlcv)
                inserted += 1
        
        await self.session.flush()
        return inserted, updated

    async def delete_range(
        self,
        symbol_id: int,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
    ) -> int:
        """Delete OHLCV records within a date range."""
        result = await self.session.execute(
            select(OhlcvModel).where(
                and_(
                    OhlcvModel.symbol_id == symbol_id,
                    OhlcvModel.timeframe == timeframe,
                    OhlcvModel.timestamp >= start_date,
                    OhlcvModel.timestamp <= end_date,
                )
            )
        )
        records = list(result.scalars().all())
        count = len(records)
        
        for record in records:
            await self.session.delete(record)
        
        await self.session.flush()
        return count

    async def count(
        self,
        symbol_id: Optional[int] = None,
        timeframe: Optional[str] = None,
    ) -> int:
        """Count OHLCV records."""
        conditions = []
        if symbol_id:
            conditions.append(OhlcvModel.symbol_id == symbol_id)
        if timeframe:
            conditions.append(OhlcvModel.timeframe == timeframe)
        
        query = select(func.count(OhlcvModel.id))
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await self.session.execute(query)
        return result.scalar()


class OhlcvAnomalyRepository:
    """Repository for OHLCV anomaly operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, anomaly_data: dict) -> OhlcvAnomalyModel:
        """Create a new anomaly record."""
        anomaly = OhlcvAnomalyModel(**anomaly_data)
        self.session.add(anomaly)
        await self.session.flush()
        await self.session.refresh(anomaly)
        return anomaly

    async def get_by_symbol(
        self,
        symbol_id: int,
        resolved: Optional[bool] = None,
        limit: int = 100,
    ) -> List[OhlcvAnomalyModel]:
        """Get anomalies for a symbol."""
        conditions = [OhlcvAnomalyModel.symbol_id == symbol_id]
        
        if resolved is not None:
            conditions.append(OhlcvAnomalyModel.is_resolved == resolved)
        
        result = await self.session.execute(
            select(OhlcvAnomalyModel)
            .where(and_(*conditions))
            .order_by(OhlcvAnomalyModel.detected_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def resolve(
        self,
        anomaly_id: int,
        notes: Optional[str] = None,
    ) -> Optional[OhlcvAnomalyModel]:
        """Mark an anomaly as resolved."""
        result = await self.session.execute(
            select(OhlcvAnomalyModel).where(OhlcvAnomalyModel.id == anomaly_id)
        )
        anomaly = result.scalar_one_or_none()
        
        if anomaly:
            anomaly.is_resolved = True
            anomaly.resolved_at = datetime.utcnow()
            if notes:
                anomaly.resolution_notes = notes
            await self.session.flush()
            await self.session.refresh(anomaly)
        
        return anomaly

    async def get_unresolved_count(self, symbol_id: int) -> int:
        """Get count of unresolved anomalies for a symbol."""
        result = await self.session.execute(
            select(func.count(OhlcvAnomalyModel.id)).where(
                and_(
                    OhlcvAnomalyModel.symbol_id == symbol_id,
                    OhlcvAnomalyModel.is_resolved == False,
                )
            )
        )
        return result.scalar()