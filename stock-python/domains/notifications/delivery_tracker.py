"""
Delivery tracker - Track notification delivery status.
"""
import logging
from typing import Optional
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import String, DateTime, Integer, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from infra.database import Base

logger = logging.getLogger(__name__)


class DeliveryStatus(str, Enum):
    """Delivery status enum."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class DeliveryChannel(str, Enum):
    """Delivery channel enum."""
    WEBSOCKET = "websocket"
    PUSH_FCM = "push_fcm"
    PUSH_APNS = "push_apns"
    PUSH_WEB = "push_web"
    EMAIL = "email"


@dataclass
class DeliveryRecord:
    """Record of a notification delivery attempt."""
    notification_id: int
    channel: DeliveryChannel
    status: DeliveryStatus
    attempt: int = 1
    error_message: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


class DeliveryTracker(Base):
    """Model for tracking notification delivery."""

    __tablename__ = "notification_delivery"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notification_id: Mapped[int] = mapped_column(Integer, ForeignKey("notifications.id"), index=True)
    channel: Mapped[DeliveryChannel] = mapped_column(SQLEnum(DeliveryChannel))
    status: Mapped[DeliveryStatus] = mapped_column(SQLEnum(DeliveryStatus), index=True)
    
    # Delivery details
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Timestamps
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class DeliveryTrackerService:
    """Service for tracking notification delivery."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_record(
        self,
        notification_id: int,
        channel: DeliveryChannel,
    ) -> DeliveryTracker:
        """Create a new delivery record."""
        record = DeliveryTracker(
            notification_id=notification_id,
            channel=channel,
            status=DeliveryStatus.PENDING,
            attempt=1,
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        
        logger.debug(f"Created delivery record {record.id} for notification {notification_id}")
        return record

    async def mark_sent(
        self,
        notification_id: int,
        channel: DeliveryChannel,
    ) -> Optional[DeliveryTracker]:
        """Mark delivery as sent."""
        from sqlalchemy import update, select
        
        # Find existing record or create new
        query = select(DeliveryTracker).where(
            DeliveryTracker.notification_id == notification_id,
            DeliveryTracker.channel == channel,
        )
        result = await self.db.execute(query)
        record = result.scalar_one_or_none()

        if record:
            record.status = DeliveryStatus.SENT
            record.sent_at = datetime.utcnow()
            record.attempt += 1
            await self.db.commit()
            await self.db.refresh(record)
            return record

        return await self.create_record(notification_id, channel)

    async def mark_delivered(
        self,
        notification_id: int,
        channel: DeliveryChannel,
    ) -> Optional[DeliveryTracker]:
        """Mark delivery as delivered."""
        from sqlalchemy import update, select
        
        query = select(DeliveryTracker).where(
            DeliveryTracker.notification_id == notification_id,
            DeliveryTracker.channel == channel,
        )
        result = await self.db.execute(query)
        record = result.scalar_one_or_none()

        if record:
            record.status = DeliveryStatus.DELIVERED
            record.delivered_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(record)
            return record

        logger.warning(f"Delivery record not found for notification {notification_id}, channel {channel}")
        return None

    async def mark_failed(
        self,
        notification_id: int,
        channel: DeliveryChannel,
        error_message: str,
    ) -> Optional[DeliveryTracker]:
        """Mark delivery as failed."""
        from sqlalchemy import update, select
        
        query = select(DeliveryTracker).where(
            DeliveryTracker.notification_id == notification_id,
            DeliveryTracker.channel == channel,
        )
        result = await self.db.execute(query)
        record = result.scalar_one_or_none()

        if record:
            record.status = DeliveryStatus.FAILED
            record.error_message = error_message
            record.attempt += 1
            await self.db.commit()
            await self.db.refresh(record)
            return record

        # Create new record if doesn't exist
        return await self.create_with_status(notification_id, channel, DeliveryStatus.FAILED, error_message)

    async def mark_retrying(
        self,
        notification_id: int,
        channel: DeliveryChannel,
    ) -> Optional[DeliveryTracker]:
        """Mark delivery as retrying."""
        from sqlalchemy import update, select
        
        query = select(DeliveryTracker).where(
            DeliveryTracker.notification_id == notification_id,
            DeliveryTracker.channel == channel,
        )
        result = await self.db.execute(query)
        record = result.scalar_one_or_none()

        if record:
            record.status = DeliveryStatus.RETRYING
            record.attempt += 1
            await self.db.commit()
            await self.db.refresh(record)
            return record

        return None

    async def create_with_status(
        self,
        notification_id: int,
        channel: DeliveryChannel,
        status: DeliveryStatus,
        error_message: Optional[str] = None,
    ) -> DeliveryTracker:
        """Create a delivery record with a specific status."""
        record = DeliveryTracker(
            notification_id=notification_id,
            channel=channel,
            status=status,
            error_message=error_message,
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def get_notification_status(
        self,
        notification_id: int,
    ) -> list[DeliveryTracker]:
        """Get all delivery records for a notification."""
        from sqlalchemy import select
        
        query = select(DeliveryTracker).where(
            DeliveryTracker.notification_id == notification_id
        ).order_by(DeliveryTracker.created_at.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_failed_deliveries(
        self,
        since: datetime = None,
        limit: int = 100,
    ) -> list[DeliveryTracker]:
        """Get failed deliveries for retry."""
        from sqlalchemy import select
        
        query = select(DeliveryTracker).where(
            DeliveryTracker.status == DeliveryStatus.FAILED
        )
        
        if since:
            query = query.where(DeliveryTracker.created_at >= since)
        
        query = query.order_by(DeliveryTracker.created_at.asc()).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_delivery_stats(
        self,
        notification_ids: list[int] = None,
    ) -> dict:
        """Get delivery statistics."""
        from sqlalchemy import select, func
        
        query = select(
            DeliveryTracker.status,
            func.count(DeliveryTracker.id).label("count")
        ).group_by(DeliveryTracker.status)

        if notification_ids:
            query = query.where(DeliveryTracker.notification_id.in_(notification_ids))

        result = await self.db.execute(query)
        stats = {row.status.value: row.count for row in result}

        return {
            "total": sum(stats.values()),
            "pending": stats.get(DeliveryStatus.PENDING.value, 0),
            "sent": stats.get(DeliveryStatus.SENT.value, 0),
            "delivered": stats.get(DeliveryStatus.DELIVERED.value, 0),
            "failed": stats.get(DeliveryStatus.FAILED.value, 0),
            "retrying": stats.get(DeliveryStatus.RETRYING.value, 0),
        }

    async def cleanup_old_records(self, days: int = 30) -> int:
        """Clean up old delivery records."""
        from sqlalchemy import delete
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        stmt = delete(DeliveryTracker).where(DeliveryTracker.created_at < cutoff)
        result = await self.db.execute(stmt)
        await self.db.commit()
        
        logger.info(f"Cleaned up {result.rowcount} old delivery records")
        return result.rowcount