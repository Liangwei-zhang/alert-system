"""
Retention worker for data pruning and archival tasks.
"""
import asyncio
import logging
from datetime import datetime, timedelta

from celery import Celery
from celery.schedules import crontab

from infra.database import async_session_maker
from domains.system.retention_service import get_retention_service
from domains.system.partition_service import get_partition_service

logger = logging.getLogger(__name__)

# Celery app configuration
celery_app = Celery("retention_worker")
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

@celery_app.task(name="retention.prune_outbox")
def prune_outbox_events(days: int = 7) -> dict:
    """Prune old completed outbox events."""
    return asyncio.run(_prune_outbox_async(days))


async def _prune_outbox_async(days: int) -> dict:
    """Async implementation of outbox pruning."""
    async with async_session_maker() as db:
        service = await get_retention_service(db)
        deleted = await service.prune_outbox_events(days)
        
        return {
            "task": "prune_outbox_events",
            "deleted": deleted,
            "timestamp": datetime.utcnow().isoformat(),
        }


@celery_app.task(name="retention.prune_dead_letter")
def prune_dead_letter_events(days: int = 30) -> dict:
    """Prune old dead letter events."""
    return asyncio.run(_prune_dead_letter_async(days))


async def _prune_dead_letter_async(days: int) -> dict:
    """Async implementation of dead letter pruning."""
    async with async_session_maker() as db:
        service = await get_retention_service(db)
        deleted = await service.prune_dead_letter(days)
        
        return {
            "task": "prune_dead_letter",
            "deleted": deleted,
            "timestamp": datetime.utcnow().isoformat(),
        }


@celery_app.task(name="retention.archive_outbox")
def archive_outbox_events(days: int = 7) -> dict:
    """Archive old completed outbox events."""
    return asyncio.run(_archive_outbox_async(days))


async def _archive_outbox_async(days: int) -> dict:
    """Async implementation of outbox archiving."""
    async with async_session_maker() as db:
        service = await get_retention_service(db)
        archived = await service.archive_outbox_events(days)
        
        return {
            "task": "archive_outbox",
            "archived": archived,
            "timestamp": datetime.utcnow().isoformat(),
        }


@celery_app.task(name="retention.get_summary")
def get_retention_summary() -> dict:
    """Get retention summary."""
    return asyncio.run(_get_summary_async())


async def _get_summary_async() -> dict:
    """Async implementation of retention summary."""
    async with async_session_maker() as db:
        service = await get_retention_service(db)
        return await service.get_retention_summary()


@celery_app.task(name="retention.partition_maintenance")
def run_partition_maintenance() -> dict:
    """Run partition maintenance tasks."""
    return asyncio.run(_partition_maintenance_async())


async def _partition_maintenance_async() -> dict:
    """Async implementation of partition maintenance."""
    async with async_session_maker() as db:
        partition_service = await get_partition_service(db)
        
        # Create today's partition
        await partition_service.create_daily_partition()
        
        # Get partitions needing maintenance
        retention_days = 30
        old_partitions = await partition_service.get_partitions_needing_maintenance(retention_days)
        
        return {
            "task": "partition_maintenance",
            "partitions_created": 1,
            "partitions_to_archive": len(old_partitions),
            "old_partitions": old_partitions,
            "timestamp": datetime.utcnow().isoformat(),
        }


# ============== Scheduler Configuration ==============

@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks for retention."""
    
    # Daily pruning at 2 AM
    sender.add_periodic_task(
        crontab(hour=2, minute=0),
        prune_outbox_events.s(7),
        name="daily_outbox_prune",
    )
    
    # Weekly dead letter pruning (Sunday 3 AM)
    sender.add_periodic_task(
        crontab(hour=3, minute=0, day_of_week=0),
        prune_dead_letter_events.s(30),
        name="weekly_dead_letter_prune",
    )
    
    # Hourly archiving
    sender.add_periodic_task(
        crontab(minute=30),
        archive_outbox_events.s(7),
        name="hourly_outbox_archive",
    )
    
    # Daily partition maintenance
    sender.add_periodic_task(
        crontab(hour=4, minute=0),
        run_partition_maintenance.s(),
        name="daily_partition_maintenance",
    )


# ============== CLI Entry Point ==============

if __name__ == "__main__":
    celery_app.start()