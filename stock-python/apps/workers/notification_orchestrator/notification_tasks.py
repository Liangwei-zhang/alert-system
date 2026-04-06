"""
Notification-related background tasks.
Integrates: template_service, batch_service, delivery_tracker, retry_service
"""
import json
import logging
from typing import Optional

from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession

from domains.notifications.notification import Notification, NotificationType, NotificationPriority
from domains.notifications.template_service import template_service, TemplateService
from domains.notifications.batch_service import BatchService, BatchConfig
from domains.notifications.delivery_tracker import DeliveryTrackerService, DeliveryChannel, DeliveryStatus
from domains.notifications.retry_service import RetryService, RetryConfig

logger = logging.getLogger(__name__)

# Initialize services
template_svc = TemplateService()
batch_config = BatchConfig(
    max_batch_size=50,
    max_wait_time_ms=5000,
    flush_on_full=True,
)
batch_svc = BatchService(batch_config)
retry_config = RetryConfig(max_retries=3, strategy="exponential")
retry_svc = RetryService(retry_config)


# === Template Service Integration ===

@shared_task(name="notification.send_signal")
def send_signal_notification(
    user_id: int,
    signal_type: str,
    symbol: str,
    price: float,
    confidence: float = 0.0,
    additional_info: str = "",
) -> dict:
    """Send signal notification using template service."""
    title, message, priority = template_svc.create_signal_notification(
        signal_type=signal_type,
        symbol=symbol,
        price=price,
        confidence=confidence,
        additional_info=additional_info,
    )

    return {
        "user_id": user_id,
        "type": signal_type,
        "title": title,
        "message": message,
        "priority": priority.value,
    }


@shared_task(name="notification.send_price_alert_task")
def send_price_alert_notification(
    user_id: int,
    symbol: str,
    price: float,
    direction: str,
    percent_change: float,
) -> dict:
    """Send price alert using template service."""
    title, message, priority = template_svc.create_price_alert(
        symbol=symbol,
        price=price,
        direction=direction,
        percent_change=percent_change,
    )

    return {
        "user_id": user_id,
        "type": "price_alert",
        "title": title,
        "message": message,
        "priority": priority.value,
    }


# === Batch Service Integration ===

@shared_task(name="notification.queue_batch")
def queue_notification_batch(notification_data: dict, user_id: int) -> Optional[dict]:
    """Queue a notification for batching."""
    # This would be called by workers producing notifications
    # The batch service handles flushing when batch is full or timer expires
    import asyncio

    # Convert to sync for Celery (in practice, use async worker)
    def add_to_batch():
        return asyncio.run(
            batch_svc.add(notification_data, user_id)
        )

    result = add_to_batch()
    if result:
        return result.to_dict()
    return None


@shared_task(name="notification.flush_user_batch")
def flush_user_notification_batch(user_id: int) -> Optional[dict]:
    """Force flush a user's notification batch."""
    import asyncio

    def flush():
        return asyncio.run(batch_svc.flush_user(user_id))

    result = flush()
    if result:
        return result.to_dict()
    return None


@shared_task(name="notification.get_batch_status")
def get_notification_batch_status() -> dict:
    """Get current batch status."""
    return batch_svc.get_batch_status()


# === Delivery Tracker Integration ===

@shared_task(name="notification.record_delivery")
def record_notification_delivery(
    notification_id: int,
    channel: str,
    status: str,
    error_message: Optional[str] = None,
) -> dict:
    """Record delivery status (called from delivery workers)."""
    # Map string to enum
    channel_enum = DeliveryChannel(channel)
    status_enum = DeliveryStatus(status)

    # This would use DB session in real implementation
    return {
        "notification_id": notification_id,
        "channel": channel,
        "status": status,
        "recorded": True,
    }


# === Retry Service Integration ===

@shared_task(name="notification.schedule_retry")
def schedule_notification_retry(
    notification_id: int,
    channel: str,
    attempt: int = 0,
    last_error: Optional[str] = None,
) -> dict:
    """Schedule a retry for a failed notification."""
    channel_enum = DeliveryChannel(channel)

    task = retry_svc.schedule_retry(
        notification_id=notification_id,
        channel=channel_enum,
        attempt=attempt,
        last_error=last_error,
    )

    return {
        "notification_id": notification_id,
        "channel": channel,
        "attempt": task.attempt,
        "next_retry_at": task.next_retry_at.isoformat(),
    }


@shared_task(name="notification.process_retries")
def process_pending_retries() -> list[dict]:
    """Process all pending notification retries."""
    import asyncio

    async def process():
        return await retry_svc.process_ready_retries()

    results = asyncio.run(process())

    return [
        {
            "notification_id": task.notification_id,
            "channel": task.channel.value,
            "attempt": task.attempt,
            "success": success,
        }
        for task, success in results
    ]


@shared_task(name="notification.get_retry_status")
def get_retry_service_status() -> dict:
    """Get retry service status."""
    return retry_svc.get_status()


# === Legacy tasks ===

@shared_task(name="notification.send_email")
def send_email_notification(recipient: str, subject: str, body: str):
    """Send email notification."""
    # TODO: Implement email sending with template + batching
    pass


@shared_task(name="notification.cleanup_old_notifications")
def cleanup_old_notifications(days: int = 30):
    """Clean up old notifications."""
    # TODO: Implement cleanup with delivery tracker cleanup
    pass