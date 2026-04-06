"""
Outbox relay service for processing and publishing outbox events.
"""
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import logging
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.models.system import OutboxEventModel

logger = logging.getLogger(__name__)


class OutboxRelayService:
    """Service for relaying outbox events to external systems."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._handlers: Dict[str, Callable] = {}

    # ============== Handler Registration ==============

    def register_handler(self, event_type: str, handler: Callable) -> None:
        """Register a handler for a specific event type."""
        self._handlers[event_type] = handler
        logger.info(f"Registered handler for event type: {event_type}")

    def get_handler(self, event_type: str) -> Optional[Callable]:
        """Get the handler for a specific event type."""
        return self._handlers.get(event_type)

    # ============== Event Processing ==============

    async def process_pending_events(
        self, 
        batch_size: int = 100,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Process all pending outbox events."""
        # Get pending events
        query = select(OutboxEventModel).where(
            OutboxEventModel.status == "pending"
        ).order_by(OutboxEventModel.created_at).limit(batch_size)
        
        result = await self.db.execute(query)
        events = list(result.scalars().all())

        processed = 0
        failed = 0
        errors = []

        for event in events:
            success = await self._process_single_event(event, max_retries)
            if success:
                processed += 1
            else:
                failed += 1
                errors.append(f"Event {event.id} failed")

        return {
            "processed": processed,
            "failed": failed,
            "errors": errors,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _process_single_event(
        self, 
        event: OutboxEventModel, 
        max_retries: int
    ) -> bool:
        """Process a single outbox event."""
        try:
            # Mark as processing
            event.status = "processing"
            await self.db.commit()

            # Get handler
            handler = self.get_handler(event.event_type)
            
            if handler is None:
                logger.warning(f"No handler registered for event type: {event.event_type}")
                event.status = "dead_letter"
                event.last_error = f"No handler for event type: {event.event_type}"
                await self.db.commit()
                return False

            # Execute handler
            try:
                await handler(event.payload, event.metadata or {})
            except Exception as e:
                logger.error(f"Handler error for event {event.id}: {str(e)}")
                event.retry_count += 1
                event.last_error = str(e)
                
                if event.retry_count >= max_retries:
                    event.status = "dead_letter"
                    logger.warning(f"Event {event.id} moved to dead letter after {max_retries} retries")
                else:
                    event.status = "pending"
                    # Simple exponential backoff
                    from datetime import timedelta
                    event.next_retry_at = datetime.utcnow() + timedelta(minutes=5 ** event.retry_count)
                
                await self.db.commit()
                return False

            # Mark as completed
            event.status = "completed"
            event.processed_at = datetime.utcnow()
            await self.db.commit()
            return True

        except Exception as e:
            logger.error(f"Error processing event {event.id}: {str(e)}")
            event.status = "pending"
            event.last_error = str(e)
            await self.db.commit()
            return False

    async def reprocess_event(self, event_id: int) -> bool:
        """Reprocess a specific event (e.g., from dead letter)."""
        try:
            query = select(OutboxEventModel).where(OutboxEventModel.id == event_id)
            result = await self.db.execute(query)
            event = result.scalar_one_or_none()
            
            if not event:
                return False

            # Reset status
            event.status = "pending"
            event.retry_count = 0
            event.last_error = None
            await self.db.commit()
            
            return True
        except Exception:
            await self.db.rollback()
            return False

    # ============== Event Queries ==============

    async def get_events_by_aggregate(
        self,
        aggregate_type: str,
        aggregate_id: str
    ) -> List[OutboxEventModel]:
        """Get all events for a specific aggregate."""
        query = select(OutboxEventModel).where(
            OutboxEventModel.aggregate_type == aggregate_type,
            OutboxEventModel.aggregate_id == aggregate_id
        ).order_by(OutboxEventModel.created_at)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_events_by_type(
        self,
        event_type: str,
        limit: int = 100
    ) -> List[OutboxEventModel]:
        """Get events by type."""
        query = select(OutboxEventModel).where(
            OutboxEventModel.event_type == event_type
        ).order_by(OutboxEventModel.created_at.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_failed_events(self, limit: int = 100) -> List[OutboxEventModel]:
        """Get failed/dead letter events."""
        query = select(OutboxEventModel).where(
            OutboxEventModel.status.in_(["failed", "dead_letter"])
        ).order_by(OutboxEventModel.created_at.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    # ============== Manual Operations ==============

    async def retry_failed_events(self, max_to_retry: int = 10) -> int:
        """Retry failed events that are within retry limits."""
        query = select(OutboxEventModel).where(
            OutboxEventModel.status == "dead_letter",
            OutboxEventModel.retry_count < OutboxEventModel.max_retries
        ).order_by(OutboxEventModel.created_at).limit(max_to_retry)
        
        result = await self.db.execute(query)
        events = list(result.scalars().all())

        retried = 0
        for event in events:
            event.status = "pending"
            event.last_error = None
            retried += 1

        await self.db.commit()
        logger.info(f"Reset {retried} dead letter events for retry")
        return retried

    async def get_event_by_id(self, event_id: int) -> Optional[OutboxEventModel]:
        """Get a specific event by ID."""
        query = select(OutboxEventModel).where(OutboxEventModel.id == event_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()


async def get_outbox_relay_service(db: AsyncSession) -> OutboxRelayService:
    """Dependency injection for OutboxRelayService."""
    return OutboxRelayService(db)