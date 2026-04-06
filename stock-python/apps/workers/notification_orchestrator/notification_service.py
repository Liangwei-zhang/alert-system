"""
Notification service - handles notification creation and delivery.
"""
import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from domains.notifications.notification import Notification, NotificationType, NotificationPriority, Device

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing notifications."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_notification(
        self,
        user_id: int,
        type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        related_type: Optional[str] = None,
        related_id: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> Notification:
        """Create a new notification."""
        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            priority=priority,
            related_type=related_type,
            related_id=related_id,
            metadata=json.dumps(metadata) if metadata else None,
        )
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        
        logger.info(f"Created notification {notification.id} for user {user_id}")
        return notification

    async def create_signal_notification(
        self,
        user_id: int,
        signal_type: str,
        symbol: str,
        price: float,
        metadata: Optional[dict] = None,
    ) -> Notification:
        """Create a signal alert notification."""
        type_map = {
            "buy": NotificationType.SIGNAL_BUY,
            "sell": NotificationType.SIGNAL_SELL,
            "split_buy": NotificationType.SIGNAL_SPLIT_BUY,
            "split_sell": NotificationType.SIGNAL_SPLIT_SELL,
        }
        
        titles = {
            "buy": f"📈 Buy Signal: {symbol}",
            "sell": f"📉 Sell Signal: {symbol}",
            "split_buy": f"🔄 Split Buy Signal: {symbol}",
            "split_sell": f"🔄 Split Sell Signal: {symbol}",
        }
        
        messages = {
            "buy": f"Buy signal triggered for {symbol} at ${price:.2f}",
            "sell": f"Sell signal triggered for {symbol} at ${price:.2f}",
            "split_buy": f"Split buy signal triggered for {symbol} at ${price:.2f}",
            "split_sell": f"Split sell signal triggered for {symbol} at ${price:.2f}",
        }

        notification_type = type_map.get(signal_type, NotificationType.SIGNAL_BUY)
        title = titles.get(signal_type, f"Signal: {symbol}")
        message = messages.get(signal_type, f"Signal triggered for {symbol} at ${price:.2f}")

        # Build metadata
        signal_metadata = metadata or {}
        signal_metadata.update({
            "symbol": symbol,
            "price": price,
            "signal_type": signal_type,
        })

        return await self.create_notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            priority=NotificationPriority.HIGH,
            related_type="signal",
            metadata=signal_metadata,
        )

    async def get_user_notifications(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        unread_only: bool = False,
    ) -> tuple[list[Notification], int]:
        """Get notifications for a user."""
        query = select(Notification).where(Notification.user_id == user_id)
        
        if unread_only:
            query = query.where(Notification.is_read == False)
        
        # Get total count
        from sqlalchemy import func
        count_query = select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
        if unread_only:
            count_query = count_query.where(Notification.is_read == False)
        result = await self.db.execute(count_query)
        total = result.scalar() or 0
        
        # Get paginated results
        query = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        notifications = list(result.scalars().all())
        
        return notifications, total

    async def get_unread_count(self, user_id: int) -> int:
        """Get count of unread notifications."""
        from sqlalchemy import func, select
        query = select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read == False
        )
        result = await self.db.execute(query)
        return result.scalar() or 0

    async def mark_as_read(self, notification_ids: list[int], user_id: int) -> int:
        """Mark notifications as read."""
        from sqlalchemy import update
        stmt = (
            update(Notification)
            .where(Notification.id.in_(notification_ids))
            .where(Notification.user_id == user_id)
            .values(
                is_read=True,
                read_at=datetime.utcnow(),
            )
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount

    async def mark_all_as_read(self, user_id: int) -> int:
        """Mark all notifications as read."""
        from sqlalchemy import update
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id)
            .where(Notification.is_read == False)
            .values(
                is_read=True,
                read_at=datetime.utcnow(),
            )
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount

    async def delete_notification(self, notification_id: int, user_id: int) -> bool:
        """Delete a notification."""
        from sqlalchemy import delete
        stmt = delete(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0

    async def get_user_devices(self, user_id: int) -> list[Device]:
        """Get user's registered devices."""
        from sqlalchemy import select
        query = select(Device).where(
            Device.user_id == user_id,
            Device.is_active == True,
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def register_device(
        self,
        user_id: int,
        platform: str,
        push_token: str,
        name: Optional[str] = None,
        push_token_expires_at: Optional[datetime] = None,
    ) -> Device:
        """Register a device for push notifications."""
        from sqlalchemy import select
        
        # Check if device with this push token already exists
        query = select(Device).where(Device.push_token == push_token)
        result = await self.db.execute(query)
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing device
            existing.name = name
            existing.platform = platform
            existing.last_used_at = datetime.utcnow()
            existing.push_token_expires_at = push_token_expires_at
            await self.db.commit()
            await self.db.refresh(existing)
            return existing
        
        # Create new device
        device = Device(
            user_id=user_id,
            platform=platform,
            push_token=push_token,
            name=name,
            push_token_expires_at=push_token_expires_at,
        )
        self.db.add(device)
        await self.db.commit()
        await self.db.refresh(device)
        
        logger.info(f"Registered device {device.id} for user {user_id}")
        return device

    async def unregister_device(self, device_id: int, user_id: int) -> bool:
        """Unregister a device."""
        from sqlalchemy import update
        stmt = (
            update(Device)
            .where(Device.id == device_id)
            .where(Device.user_id == user_id)
            .values(is_active=False)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0

    async def update_device_last_used(self, device_id: int) -> None:
        """Update device last used timestamp."""
        from sqlalchemy import update
        stmt = (
            update(Device)
            .where(Device.id == device_id)
            .values(last_used_at=datetime.utcnow())
        )
        await self.db.execute(stmt)
        await self.db.commit()


# WebSocket notification broadcaster
class NotificationBroadcaster:
    """Broadcasts notifications via WebSocket."""

    def __init__(self):
        self.connections: dict[int, list] = {}  # user_id -> list of WebSocket connections

    def add_connection(self, user_id: int, websocket):
        """Add a WebSocket connection for a user."""
        if user_id not in self.connections:
            self.connections[user_id] = []
        self.connections[user_id].append(websocket)
        logger.info(f"WebSocket connection added for user {user_id}")

    def remove_connection(self, user_id: int, websocket):
        """Remove a WebSocket connection for a user."""
        if user_id in self.connections:
            self.connections[user_id] = [ws for ws in self.connections[user_id] if ws != websocket]
            if not self.connections[user_id]:
                del self.connections[user_id]
            logger.info(f"WebSocket connection removed for user {user_id}")

    async def broadcast(self, user_id: int, notification: Notification):
        """Broadcast a notification to all connected WebSockets for a user."""
        if user_id not in self.connections:
            return
        
        from domains.notifications.notification import NotificationResponse
        
        # Convert to response schema
        notification_data = NotificationResponse.from_orm(notification)
        
        # Send to all connections
        disconnected = []
        for ws in self.connections[user_id]:
            try:
                await ws.send_json({
                    "type": "notification",
                    "data": notification_data.model_dump(),
                })
            except Exception as e:
                logger.error(f"Error sending notification via WebSocket: {e}")
                disconnected.append(ws)
        
        # Remove disconnected connections
        for ws in disconnected:
            self.remove_connection(user_id, ws)


# Global broadcaster instance
notification_broadcaster = NotificationBroadcaster()
