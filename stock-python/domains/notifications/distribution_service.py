"""
Distribution service - handles message queue management, priority delivery, and receipts.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_, func, desc

from domains.notifications.distribution import (
    MessageQueue, 
    DeliveryReceipt, 
    ArchivedMessage,
    DistributionStatus, 
    DistributionPriority,
    DeliveryReceiptStatus,
)

logger = logging.getLogger(__name__)


class DistributionService:
    """Service for managing message distribution."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # Queue Management
    # =========================================================================

    async def enqueue_message(
        self,
        user_id: int,
        title: str,
        message: str,
        channel: str = "in_app",
        priority: DistributionPriority = DistributionPriority.NORMAL,
        notification_id: Optional[int] = None,
        metadata: Optional[dict] = None,
        scheduled_at: Optional[datetime] = None,
        max_retries: int = 3,
    ) -> MessageQueue:
        """Add a message to the distribution queue."""
        queue_item = MessageQueue(
            notification_id=notification_id,
            user_id=user_id,
            channel=channel,
            priority=priority,
            status=DistributionStatus.PENDING,
            title=title,
            message=message,
            metadata=json.dumps(metadata) if metadata else None,
            scheduled_at=scheduled_at,
            max_retries=max_retries,
        )
        
        self.db.add(queue_item)
        await self.db.commit()
        await self.db.refresh(queue_item)
        
        logger.info(f"Enqueued message {queue_item.id} for user {user_id} via {channel}")
        return queue_item

    async def get_pending_messages(
        self,
        channel: Optional[str] = None,
        priority: Optional[DistributionPriority] = None,
        limit: int = 100,
    ) -> list[MessageQueue]:
        """Get pending messages ready for processing."""
        query = select(MessageQueue).where(
            and_(
                MessageQueue.status == DistributionStatus.PENDING,
                or_(
                    MessageQueue.scheduled_at.is_(None),
                    MessageQueue.scheduled_at <= datetime.utcnow()
                )
            )
        )
        
        if channel:
            query = query.where(MessageQueue.channel == channel)
        if priority:
            query = query.where(MessageQueue.priority == priority)
        
        # Order by priority (urgent first), then by created_at
        query = query.order_by(
            desc(MessageQueue.priority),
            MessageQueue.created_at.asc()
        ).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def mark_processing(self, queue_id: int) -> Optional[MessageQueue]:
        """Mark message as being processed."""
        await self.db.execute(
            update(MessageQueue)
            .where(MessageQueue.id == queue_id)
            .values(
                status=DistributionStatus.PROCESSING,
                processed_at=datetime.utcnow(),
            )
        )
        await self.db.commit()
        
        result = await self.db.execute(
            select(MessageQueue).where(MessageQueue.id == queue_id)
        )
        return result.scalar_one_or_none()

    async def mark_delivered(
        self, 
        queue_id: int, 
        channel_delivery_id: Optional[str] = None,
    ) -> Optional[MessageQueue]:
        """Mark message as delivered."""
        now = datetime.utcnow()
        
        await self.db.execute(
            update(MessageQueue)
            .where(MessageQueue.id == queue_id)
            .values(
                status=DistributionStatus.DELIVERED,
                delivered_at=now,
            )
        )
        
        # Create delivery receipt
        receipt = DeliveryReceipt(
            queue_id=queue_id,
            channel_delivery_id=channel_delivery_id,
            status=DeliveryReceiptStatus.DELIVERED,
            delivered_at=now,
        )
        self.db.add(receipt)
        await self.db.commit()
        
        result = await self.db.execute(
            select(MessageQueue).where(MessageQueue.id == queue_id)
        )
        return result.scalar_one_or_none()

    async def mark_failed(
        self,
        queue_id: int,
        error_message: str,
        error_code: Optional[str] = None,
    ) -> Optional[MessageQueue]:
        """Mark message as failed."""
        result = await self.db.execute(
            select(MessageQueue).where(MessageQueue.id == queue_id)
        )
        queue = result.scalar_one_or_none()
        
        if not queue:
            return None
        
        # Check if we should retry
        if queue.retry_count < queue.max_retries:
            queue.status = DistributionStatus.PENDING
            queue.retry_count += 1
            queue.last_retry_at = datetime.utcnow()
            queue.error_message = error_message
            queue.error_count += 1
        else:
            queue.status = DistributionStatus.FAILED
            queue.error_message = error_message
        
        await self.db.commit()
        
        # Create failure receipt
        receipt = DeliveryReceipt(
            queue_id=queue_id,
            status=DeliveryReceiptStatus.FAILED,
            failed_at=datetime.utcnow(),
            error_code=error_code,
            error_message=error_message,
        )
        self.db.add(receipt)
        await self.db.commit()
        
        return queue

    async def get_queue_stats(self) -> dict:
        """Get queue statistics."""
        stats_query = await self.db.execute(
            select(
                MessageQueue.status,
                func.count(MessageQueue.id)
            ).group_by(MessageQueue.status)
        )
        
        status_counts = {}
        for status, count in stats_query.all():
            status_counts[status.value] = count
        
        # Priority breakdown for pending
        priority_query = await self.db.execute(
            select(
                MessageQueue.priority,
                func.count(MessageQueue.id)
            ).where(
                MessageQueue.status == DistributionStatus.PENDING
            ).group_by(MessageQueue.priority)
        )
        
        priority_counts = {}
        for priority, count in priority_query.all():
            priority_counts[priority.value] = count
        
        return {
            "total": sum(status_counts.values()),
            "pending": status_counts.get(DistributionStatus.PENDING.value, 0),
            "processing": status_counts.get(DistributionStatus.PROCESSING.value, 0),
            "delivered": status_counts.get(DistributionStatus.DELIVERED.value, 0),
            "failed": status_counts.get(DistributionStatus.FAILED.value, 0),
            "escalated": status_counts.get(DistributionStatus.ESCALATED.value, 0),
            "by_priority": priority_counts,
        }

    # =========================================================================
    # Receipt Tracking
    # =========================================================================

    async def get_receipts_for_queue(self, queue_id: int) -> list[DeliveryReceipt]:
        """Get all receipts for a queue item."""
        result = await self.db.execute(
            select(DeliveryReceipt)
            .where(DeliveryReceipt.queue_id == queue_id)
            .order_by(DeliveryReceipt.created_at.asc())
        )
        return list(result.scalars().all())

    async def update_receipt_status(
        self,
        receipt_id: int,
        status: DeliveryReceiptStatus,
        channel_response: Optional[dict] = None,
    ) -> Optional[DeliveryReceipt]:
        """Update receipt status."""
        update_values = {"status": status}
        
        if status == DeliveryReceiptStatus.SENT:
            update_values["sent_at"] = datetime.utcnow()
        elif status == DeliveryReceiptStatus.DELIVERED:
            update_values["delivered_at"] = datetime.utcnow()
        elif status == DeliveryReceiptStatus.READ:
            update_values["read_at"] = datetime.utcnow()
        elif status == DeliveryReceiptStatus.FAILED:
            update_values["failed_at"] = datetime.utcnow()
        
        if channel_response:
            update_values["channel_response"] = json.dumps(channel_response)
        
        await self.db.execute(
            update(DeliveryReceipt)
            .where(DeliveryReceipt.id == receipt_id)
            .values(**update_values)
        )
        await self.db.commit()
        
        result = await self.db.execute(
            select(DeliveryReceipt).where(DeliveryReceipt.id == receipt_id)
        )
        return result.scalar_one_or_none()

    # =========================================================================
    # Escalation
    # =========================================================================

    async def escalate_message(
        self,
        queue_id: int,
        note: Optional[str] = None,
    ) -> Optional[MessageQueue]:
        """Escalate a message for manual review."""
        result = await self.db.execute(
            select(MessageQueue).where(MessageQueue.id == queue_id)
        )
        queue = result.scalar_one_or_none()
        
        if not queue:
            return None
        
        queue.status = DistributionStatus.ESCALATED
        queue.escalation_level += 1
        queue.escalated_at = datetime.utcnow()
        queue.escalation_note = note
        
        await self.db.commit()
        
        logger.warning(f"Escalated message {queue_id} to level {queue.escalation_level}")
        return queue

    async def get_escalated_messages(self, limit: int = 50) -> list[MessageQueue]:
        """Get escalated messages."""
        result = await self.db.execute(
            select(MessageQueue)
            .where(MessageQueue.status == DistributionStatus.ESCALATED)
            .order_by(MessageQueue.escalated_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # =========================================================================
    # Archiving
    # =========================================================================

    async def archive_message(
        self,
        queue_id: int,
        reason: str = "completed",
    ) -> Optional[ArchivedMessage]:
        """Archive a completed or failed message."""
        result = await self.db.execute(
            select(MessageQueue).where(MessageQueue.id == queue_id)
        )
        queue = result.scalar_one_or_none()
        
        if not queue:
            return None
        
        # Get final receipt status
        receipt_result = await self.db.execute(
            select(DeliveryReceipt)
            .where(DeliveryReceipt.queue_id == queue_id)
            .order_by(DeliveryReceipt.created_at.desc())
            .limit(1)
        )
        receipt = receipt_result.scalar_one_or_none()
        
        # Create archived message
        archived = ArchivedMessage(
            original_queue_id=queue.id,
            original_notification_id=queue.notification_id,
            user_id=queue.user_id,
            channel=queue.channel,
            title=queue.title,
            message=queue.message,
            status=queue.status,
            delivered_at=queue.delivered_at,
            retry_count=queue.retry_count,
            final_error=queue.error_message,
            receipt_status=receipt.status if receipt else DeliveryReceiptStatus.PENDING,
            metadata=queue.metadata,
            archive_reason=reason,
            original_created_at=queue.created_at,
            original_updated_at=queue.updated_at,
        )
        
        self.db.add(archived)
        
        # Update queue status to archived
        queue.status = DistributionStatus.ARCHIVED
        
        await self.db.commit()
        await self.db.refresh(archived)
        
        logger.info(f"Archived message {queue_id} (reason: {reason})")
        return archived

    async def archive_completed(
        self,
        days_old: int = 30,
        limit: int = 1000,
    ) -> int:
        """Archive old completed messages."""
        cutoff = datetime.utcnow() - timedelta(days=days_old)
        
        # Find completed messages older than cutoff
        result = await self.db.execute(
            select(MessageQueue)
            .where(
                and_(
                    MessageQueue.status == DistributionStatus.DELIVERED,
                    MessageQueue.updated_at < cutoff
                )
            )
            .limit(limit)
        )
        
        queues = list(result.scalars().all())
        archived_count = 0
        
        for queue in queues:
            await self.archive_message(queue.id, reason="completed")
            archived_count += 1
        
        logger.info(f"Archived {archived_count} completed messages")
        return archived_count

    async def archive_failed_max_retries(
        self,
        limit: int = 500,
    ) -> int:
        """Archive messages that exceeded max retries."""
        result = await self.db.execute(
            select(MessageQueue)
            .where(
                and_(
                    MessageQueue.status == DistributionStatus.FAILED,
                    MessageQueue.retry_count >= MessageQueue.max_retries,
                )
            )
            .limit(limit)
        )
        
        queues = list(result.scalars().all())
        archived_count = 0
        
        for queue in queues:
            await self.archive_message(queue.id, reason="failed_max_retries")
            archived_count += 1
        
        logger.info(f"Archived {archived_count} failed messages")
        return archived_count

    async def get_archived_messages(
        self,
        user_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ArchivedMessage]:
        """Get archived messages."""
        query = select(ArchivedMessage).order_by(
            ArchivedMessage.archived_at.desc()
        )
        
        if user_id:
            query = query.where(ArchivedMessage.user_id == user_id)
        
        result = await self.db.execute(
            query.offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    # =========================================================================
    # Priority Helpers
    # =========================================================================

    async def get_next_message(self) -> Optional[MessageQueue]:
        """Get the highest priority message next in queue."""
        result = await self.db.execute(
            select(MessageQueue)
            .where(
                and_(
                    MessageQueue.status == DistributionStatus.PENDING,
                    or_(
                        MessageQueue.scheduled_at.is_(None),
                        MessageQueue.scheduled_at <= datetime.utcnow()
                    )
                )
            )
            .order_by(
                desc(MessageQueue.priority),
                MessageQueue.created_at.asc()
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_user(
        self,
        user_id: int,
        limit: int = 50,
    ) -> list[MessageQueue]:
        """Get all queue messages for a user."""
        result = await self.db.execute(
            select(MessageQueue)
            .where(MessageQueue.user_id == user_id)
            .order_by(MessageQueue.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_notification(
        self,
        notification_id: int,
    ) -> list[MessageQueue]:
        """Get all queue messages for a notification."""
        result = await self.db.execute(
            select(MessageQueue)
            .where(MessageQueue.notification_id == notification_id)
        )
        return list(result.scalars().all())