"""
Partition service for time-series data partitioning.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.models.system import OutboxEventModel, RuntimeMetricModel

logger = logging.getLogger(__name__)


class PartitionService:
    """Service for managing time-series partitions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============== Partition Management ==============

    async def ensure_partition_exists(
        self, 
        table_name: str, 
        partition_date: str
    ) -> bool:
        """
        Ensure a partition exists for the given date.
        
        Note: This is a simplified version. In production with 
        PostgreSQL, you'd use native table partitioning.
        """
        # In production, this would create partitions
        # For now, we just ensure the partition_date is set
        logger.debug(f"Ensuring partition {table_name}/{partition_date} exists")
        return True

    async def get_partition_info(self, table_name: str) -> List[Dict[str, Any]]:
        """Get information about existing partitions."""
        # Simplified - return current month info
        now = datetime.utcnow()
        return [
            {
                "partition": f"{table_name}_{now.strftime('%Y_%m')}",
                "start_date": now.replace(day=1).isoformat(),
                "end_date": (now.replace(day=28) + timedelta(days=4)).replace(day=1).isoformat(),
                "row_count": 0,
            }
        ]

    # ============== Outbox Partitioning ==============

    async def get_outbox_by_partition(
        self, 
        partition_date: str, 
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[OutboxEventModel]:
        """Get outbox events by partition date."""
        query = select(OutboxEventModel).where(
            OutboxEventModel.partition_date == partition_date
        )
        
        if status:
            query = query.where(OutboxEventModel.status == status)
        
        query = query.order_by(OutboxEventModel.created_at).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_partition_stats(self) -> Dict[str, Any]:
        """Get partition statistics for outbox events."""
        query = select(
            OutboxEventModel.partition_date,
            OutboxEventModel.status,
            func.count(OutboxEventModel.id).label("count")
        ).group_by(
            OutboxEventModel.partition_date,
            OutboxEventModel.status
        )
        
        result = await self.db.execute(query)
        
        partitions = {}
        for row in result:
            if row.partition_date not in partitions:
                partitions[row.partition_date] = {}
            partitions[row.partition_date][row.status] = row.count

        return {
            "partitions": partitions,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def create_daily_partition(self, date: Optional[datetime] = None) -> bool:
        """Create or ensure a daily partition exists."""
        if date is None:
            date = datetime.utcnow()
        
        partition_date = date.strftime("%Y-%m-%d")
        return await self.ensure_partition_exists("outbox_events", partition_date)

    # ============== Partition Maintenance ==============

    async def get_oldest_partition_date(self) -> Optional[str]:
        """Get the oldest partition date with data."""
        query = select(OutboxEventModel.partition_date).order_by(
            OutboxEventModel.partition_date.asc()
        ).limit(1)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_partition_size(self, partition_date: str) -> int:
        """Get row count for a specific partition."""
        query = select(func.count(OutboxEventModel.id)).where(
            OutboxEventModel.partition_date == partition_date
        )
        
        result = await self.db.execute(query)
        return result.scalar() or 0

    async def get_partitions_needing_maintenance(
        self, 
        retention_days: int = 30
    ) -> List[str]:
        """Get partitions that should be archived or pruned."""
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")
        
        query = select(OutboxEventModel.partition_date).where(
            OutboxEventModel.partition_date < cutoff_str
        ).distinct()
        
        result = await self.db.execute(query)
        return [row.partition_date for row in result]


async def get_partition_service(db: AsyncSession) -> PartitionService:
    """Dependency injection for PartitionService."""
    return PartitionService(db)