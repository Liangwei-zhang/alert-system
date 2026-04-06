"""
Outbox relay worker for processing and publishing outbox events.
"""
import asyncio
import logging
from datetime import datetime

from celery import Celery
from celery.schedules import crontab

from infra.database import async_session_maker
from domains.system.outbox_relay_service import get_outbox_relay_service

logger = logging.getLogger(__name__)

# Celery app configuration
celery_app = Celery("outbox_relay_worker")
celery_app.conf.update(
    broker_url="redis://localhost:6379/0",
    result_backend="redis://localhost:6379/0",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


# ============== Celery Tasks ==============

@celery_app.task(name="outbox.process_pending", bind=True, max_retries=3)
def process_pending_outbox_events(self, batch_size: int = 100) -> dict:
    """Process all pending outbox events."""
    return asyncio.run(_process_pending_async(batch_size))


async def _process_pending_async(batch_size: int) -> dict:
    """Async implementation of pending event processing."""
    async with async_session_maker() as db:
        service = await get_outbox_relay_service(db)
        result = await service.process_pending_events(batch_size=batch_size)
        
        logger.info(f"Processed {result['processed']} events, {result['failed']} failed")
        return result


@celery_app.task(name="outbox.retry_failed", bind=True)
def retry_failed_outbox_events(self, max_to_retry: int = 10) -> dict:
    """Retry failed/dead letter events."""
    return asyncio.run(_retry_failed_async(max_to_retry))


async def _retry_failed_async(max_to_retry: int) -> dict:
    """Async implementation of failed event retry."""
    async with async_session_maker() as db:
        service = await get_outbox_relay_service(db)
        retried = await service.retry_failed_events(max_to_retry)
        
        return {
            "task": "retry_failed",
            "retried": retried,
            "timestamp": datetime.utcnow().isoformat(),
        }


@celery_app.task(name="outbox.reprocess_event")
def reprocess_single_event(event_id: int) -> dict:
    """Reprocess a specific event by ID."""
    return asyncio.run(_reprocess_single_async(event_id))


async def _reprocess_single_async(event_id: int) -> dict:
    """Async implementation of single event reprocessing."""
    async with async_session_maker() as db:
        service = await get_outbox_relay_service(db)
        success = await service.reprocess_event(event_id)
        
        return {
            "task": "reprocess_event",
            "event_id": event_id,
            "success": success,
            "timestamp": datetime.utcnow().isoformat(),
        }


@celery_app.task(name="outbox.get_failed_events")
def get_failed_outbox_events(limit: int = 100) -> dict:
    """Get failed/dead letter events."""
    return asyncio.run(_get_failed_async(limit))


async def _get_failed_async(limit: int) -> dict:
    """Async implementation of getting failed events."""
    async with async_session_maker() as db:
        service = await get_outbox_relay_service(db)
        events = await service.get_failed_events(limit)
        
        return {
            "task": "get_failed_events",
            "count": len(events),
            "events": [
                {
                    "id": e.id,
                    "aggregate_type": e.aggregate_type,
                    "aggregate_id": e.aggregate_id,
                    "event_type": e.event_type,
                    "status": e.status,
                    "retry_count": e.retry_count,
                    "last_error": e.last_error,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in events
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }


# ============== Event Handler Registration ==============

async def register_event_handlers():
    """Register event handlers for different event types."""
    async with async_session_maker() as db:
        service = await get_outbox_relay_service(db)
        
        # Register handlers for different event types
        # Example: service.register_handler("user.created", handle_user_created)
        # Example: service.register_handler("order.completed", handle_order_completed)
        
        logger.info("Event handlers registered")


# ============== Scheduler Configuration ==============

@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks for outbox relay."""
    
    # Process pending events every minute
    sender.add_periodic_task(
        crontab(second=0),
        process_pending_outbox_events.s(100),
        name="process_pending_outbox",
    )
    
    # Retry failed events every 5 minutes
    sender.add_periodic_task(
        crontab(minute="*/5"),
        retry_failed_outbox_events.s(10),
        name="retry_failed_outbox",
    )


# ============== CLI Entry Point ==============

if __name__ == "__main__":
    # Register handlers before starting
    asyncio.run(register_event_handlers())
    celery_app.start()