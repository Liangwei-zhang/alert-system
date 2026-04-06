"""
Data retention service for archiving and pruning old data.
"""
from typing import Dict, Any, List, Optional, Type
from datetime import datetime, timedelta
import logging

from sqlalchemy import select, delete, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.models.system import OutboxEventModel

logger = logging.getLogger(__name__)


class RetentionService:
    """Service for data retention, archiving, and pruning."""

    # Default retention periods (in days)
    DEFAULT_RETENTION_PERIODS = {
        "outbox_events": 7,
        "runtime_metrics": 30,
        "audit_logs": 90,
        "session_data": 30,
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============== Retention Policy Management ==============

    async def get_retention_policy(self, table_name: str) -> int:
        """Get retention period (days) for a table."""
        return self.DEFAULT_RETENTION_PERIODS.get(table_name, 30)

    async def set_retention_policy(self, table_name: str, days: int) -> bool:
        """Set retention period for a table."""
        if table_name in self.DEFAULT_RETENTION_PERIODS:
            self.DEFAULT_RETENTION_PERIODS[table_name] = days
            return True
        return False

    # ============== Outbox Event Retention ==============

    async def get_outbox_stats(self) -> Dict[str, Any]:
        """Get outbox event statistics."""
        query = select(
            OutboxEventModel.status,
            func.count(OutboxEventModel.id).label("count")
        ).group_by(OutboxEventModel.status)
        
        result = await self.db.execute(query)
        status_counts = {row.status: row.count for row in result}
        
        # Total counts
        total_query = select(func.count(OutboxEventModel.id))
        total_result = await self.db.execute(total_query)
        total_count = total_result.scalar() or 0

        return {
            "total": total_count,
            "by_status": status_counts,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def get_pending_outbox_events(
        self, 
        limit: int = 100,
        include_dead_letter: bool = False
    ) -> List[OutboxEventModel]:
        """Get pending outbox events for processing."""
        query = select(OutboxEventModel).where(
            and_(
                OutboxEventModel.status.in_(["pending", "processing"]),
                OutboxEventModel.next_retry_at <= datetime.utcnow()
            )
        ).order_by(OutboxEventModel.created_at).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def mark_outbox_processing(self, event_id: int) -> bool:
        """Mark an outbox event as processing."""
        try:
            query = select(OutboxEventModel).where(OutboxEventModel.id == event_id)
            result = await self.db.execute(query)
            event = result.scalar_one_or_none()
            
            if event:
                event.status = "processing"
                await self.db.commit()
                return True
            return False
        except Exception:
            await self.db.rollback()
            return False

    async def mark_outbox_completed(self, event_id: int) -> bool:
        """Mark an outbox event as completed."""
        try:
            query = select(OutboxEventModel).where(OutboxEventModel.id == event_id)
            result = await self.db.execute(query)
            event = result.scalar_one_or_none()
            
            if event:
                event.status = "completed"
                event.processed_at = datetime.utcnow()
                await self.db.commit()
                return True
            return False
        except Exception:
            await self.db.rollback()
            return False

    async def mark_outbox_failed(
        self, 
        event_id: int, 
        error: str,
        max_retries: int = 3
    ) -> bool:
        """Mark an outbox event as failed, with retry logic."""
        try:
            query = select(OutboxEventModel).where(OutboxEventModel.id == event_id)
            result = await self.db.execute(query)
            event = result.scalar_one_or_none()
            
            if event:
                event.retry_count += 1
                event.last_error = error
                
                if event.retry_count >= max_retries:
                    event.status = "dead_letter"
                    logger.warning(f"Outbox event {event_id} moved to dead letter after {event.retry_count} retries")
                else:
                    event.status = "pending"
                    event.next_retry_at = datetime.utcnow() + timedelta(minutes=5 * event.retry_count)
                
                await self.db.commit()
                return True
            return False
        except Exception:
            await self.db.rollback()
            return False

    async def create_outbox_event(
        self,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[OutboxEventModel]:
        """Create a new outbox event."""
        try:
            # Determine partition date
            partition_date = datetime.utcnow().strftime("%Y-%m-%d")
            
            event = OutboxEventModel(
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                event_type=event_type,
                payload=payload,
                metadata=metadata,
                status="pending",
                partition_date=partition_date,
            )
            self.db.add(event)
            await self.db.commit()
            await self.db.refresh(event)
            return event
        except Exception:
            await self.db.rollback()
            return None

    # ============== Pruning / Archiving ==============

    async def prune_outbox_events(self, days: Optional[int] = None) -> int:
        """Prune old completed outbox events."""
        if days is None:
            days = await self.get_retention_policy("outbox_events")

        cutoff = datetime.utcnow() - timedelta(days=days)
        
        query = delete(OutboxEventModel).where(
            and_(
                OutboxEventModel.status == "completed",
                OutboxEventModel.processed_at < cutoff
            )
        )
        
        result = await self.db.execute(query)
        await self.db.commit()
        
        deleted_count = result.rowcount
        logger.info(f"Pruned {deleted_count} completed outbox events older than {days} days")
        return deleted_count

    async def prune_dead_letter(self, days: int = 30) -> int:
        """Prune old dead letter events."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        query = delete(OutboxEventModel).where(
            and_(
                OutboxEventModel.status == "dead_letter",
                OutboxEventModel.created_at < cutoff
            )
        )
        
        result = await self.db.execute(query)
        await self.db.commit()
        
        deleted_count = result.rowcount
        logger.info(f"Pruned {deleted_count} dead letter events older than {days} days")
        return deleted_count

    async def archive_outbox_events(self, days: int = 7) -> int:
        """Archive old outbox events (mark for export/archival)."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # For now, just mark them - in production this would trigger actual archival
        query = select(OutboxEventModel).where(
            and_(
                OutboxEventModel.status == "completed",
                OutboxEventModel.processed_at < cutoff
            )
        ).limit(1000)
        
        result = await self.db.execute(query)
        events = list(result.scalars().all())
        
        # In production, export to cold storage here
        logger.info(f"Archive batch: {len(events)} events")
        return len(events)

    async def get_retention_summary(self) -> Dict[str, Any]:
        """Get retention summary with counts."""
        outbox_stats = await self.get_outbox_stats()
        
        # Calculate potential prune candidates
        prune_days = await self.get_retention_policy("outbox_events")
        cutoff = datetime.utcnow() - timedelta(days=prune_days)
        
        prune_query = select(func.count(OutboxEventModel.id)).where(
            and_(
                OutboxEventModel.status == "completed",
                OutboxEventModel.processed_at < cutoff
            )
        )
        prune_result = await self.db.execute(prune_query)
        prune_candidates = prune_result.scalar() or 0

        return {
            "outbox": outbox_stats,
            "retention_policy": self.DEFAULT_RETENTION_PERIODS,
            "prune_candidates": prune_candidates,
            "timestamp": datetime.utcnow().isoformat(),
        }


async def get_retention_service(db: AsyncSession) -> RetentionService:
    """Dependency injection for RetentionService."""
    return RetentionService(db)