"""
Message tasks - High-level Celery tasks for notification processing.
"""
import logging
from typing import Optional
from datetime import datetime, timedelta

from celery import shared_task
from sqlalchemy import and_, or_

from infra.database import get_db_session
from domains.notifications.notification import Notification, NotificationType, NotificationPriority

logger = logging.getLogger(__name__)


# =============================================================================
# Message Queue Processing Tasks
# =============================================================================

@shared_task(
    name="message.process_high_priority",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def process_high_priority_messages(self, limit: int = 50) -> dict:
    """
    Process high priority notifications immediately.
    
    These are time-critical notifications that need immediate processing.
    """
    logger.info(f"Processing high priority messages (limit: {limit})")
    
    session = next(get_db_session())
    
    # Get high priority pending notifications
    messages = (
        session.query(Notification)
        .filter(
            and_(
                Notification.is_read == False,
                Notification.priority == NotificationPriority.HIGH,
            )
        )
        .order_by(Notification.created_at.asc())
        .limit(limit)
        .all()
    )
    
    processed = 0
    failed = 0
    
    for message in messages:
        try:
            _process_notification(message, session)
            processed += 1
        except Exception as e:
            logger.error(f"Failed to process message {message.id}: {e}")
            failed += 1

    logger.info(f"High priority processing: {processed} done, {failed} failed")
    return {"processed": processed, "failed": failed, "total": len(messages)}


@shared_task(
    name="message.process_normal_priority",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def process_normal_priority_messages(self, limit: int = 100) -> dict:
    """
    Process normal priority notifications.
    
    These are standard notifications processed in batch.
    """
    logger.info(f"Processing normal priority messages (limit: {limit})")
    
    session = next(get_db_session())
    
    messages = (
        session.query(Notification)
        .filter(
            and_(
                Notification.is_read == False,
                Notification.priority == NotificationPriority.NORMAL,
            )
        )
        .order_by(Notification.created_at.asc())
        .limit(limit)
        .all()
    )
    
    processed = 0
    failed = 0
    
    for message in messages:
        try:
            _process_notification(message, session)
            processed += 1
        except Exception as e:
            logger.error(f"Failed to process message {message.id}: {e}")
            failed += 1

    logger.info(f"Normal priority processing: {processed} done, {failed} failed")
    return {"processed": processed, "failed": failed, "total": len(messages)}


def _process_notification(message: Notification, session) -> bool:
    """
    Process a single notification message.
    
    This is the core message processing logic that handles different
    notification types and routes them appropriately.
    """
    import json
    
    # Mark as processing
    metadata = json.loads(message.metadata or "{}")
    metadata["processed_started_at"] = datetime.utcnow().isoformat()
    metadata["status"] = "processing"
    message.metadata = json.dumps(metadata)
    
    # Route based on type
    if message.type in [
        NotificationType.SIGNAL_BUY,
        NotificationType.SIGNAL_SELL,
        NotificationType.SIGNAL_SPLIT_BUY,
        NotificationType.SIGNAL_SPLIT_SELL,
    ]:
        _handle_signal_type(message, session)
    elif message.type == NotificationType.PRICE_ALERT:
        _handle_price_alert_type(message, session)
    elif message.type == NotificationType.SYSTEM:
        _handle_system_type(message, session)
    else:
        logger.warning(f"Unknown notification type: {message.type}")
    
    # Mark as completed
    message.is_read = True
    message.read_at = datetime.utcnow()
    
    metadata = json.loads(message.metadata or "{}")
    metadata["processed_completed_at"] = datetime.utcnow().isoformat()
    metadata["status"] = "completed"
    message.metadata = json.dumps(metadata)
    
    session.commit()
    return True


def _handle_signal_type(message: Notification, session):
    """Handle signal-type notifications."""
    import json
    
    metadata = json.loads(message.metadata or "{}")
    signal_type_map = {
        NotificationType.SIGNAL_BUY: "buy",
        NotificationType.SIGNAL_SELL: "sell",
        NotificationType.SIGNAL_SPLIT_BUY: "split_buy",
        NotificationType.SIGNAL_SPLIT_SELL: "split_sell",
    }
    
    signal_type = signal_type_map.get(message.type, "unknown")
    symbol = metadata.get("symbol", "UNKNOWN")
    price = metadata.get("price", 0.0)
    
    logger.info(f"Signal notification: {signal_type} {symbol} @ ${price}")
    
    # Queue email task
    from app.tasks.email_tasks import send_signal_email_task
    
    send_signal_email_task.delay(
        user_id=message.user_id,
        signal_type=signal_type,
        symbol=symbol,
        price=price,
        message_id=message.id,
    )


def _handle_price_alert_type(message: Notification, session):
    """Handle price alert notifications."""
    import json
    
    metadata = json.loads(message.metadata or "{}")
    symbol = metadata.get("symbol", "UNKNOWN")
    current_price = metadata.get("current_price", 0.0)
    target_price = metadata.get("target_price", 0.0)
    
    logger.info(f"Price alert: {symbol} hit ${current_price} (target: ${target_price})")
    
    # Queue email task
    from app.tasks.email_tasks import send_price_alert_email_task
    
    send_price_alert_email_task.delay(
        user_id=message.user_id,
        symbol=symbol,
        current_price=current_price,
        target_price=target_price,
        message_id=message.id,
    )


def _handle_system_type(message: Notification, session):
    """Handle system notifications (log only, no email)."""
    logger.info(f"System notification: {message.title} - {message.message}")


# =============================================================================
# Retry and Recovery Tasks
# =============================================================================

@shared_task(
    name="message.retry_pending",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def retry_pending_messages(self, max_retries: int = 3) -> dict:
    """
    Retry failed messages that haven't exceeded retry limit.
    """
    logger.info(f"Retrying pending messages (max_retries: {max_retries})")
    
    session = next(get_db_session())
    
    # Find messages with processing errors that can be retried
    messages = (
        session.query(Notification)
        .filter(
            and_(
                Notification.is_read == True,  # Previously processed
                Notification.read_at >= datetime.utcnow() - timedelta(hours=1),
            )
        )
        .all()
    )
    
    retried = 0
    skipped = 0
    
    for message in messages:
        import json
        metadata = json.loads(message.metadata or "{}")
        
        retry_count = metadata.get("retry_count", 0)
        
        if retry_count < max_retries and metadata.get("status") == "failed":
            # Reset for retry
            message.is_read = False
            message.read_at = None
            metadata["retry_count"] = retry_count + 1
            metadata["status"] = "retry"
            metadata[f"retry_{retry_count + 1}_at"] = datetime.utcnow().isoformat()
            message.metadata = json.dumps(metadata)
            session.commit()
            
            # Reprocess
            try:
                _process_notification(message, session)
                retried += 1
            except Exception as e:
                logger.error(f"Retry failed for message {message.id}: {e}")
                skipped += 1
        else:
            skipped += 1

    logger.info(f"Retry complete: {retried} retried, {skipped} skipped")
    return {"retried": retried, "skipped": skipped}


# =============================================================================
# Maintenance Tasks
# =============================================================================

@shared_task(name="message.cleanup_completed")
def cleanup_completed_messages(days: int = 30) -> dict:
    """
    Clean up old completed notifications.
    
    Args:
        days: Number of days to keep completed messages
    """
    logger.info(f"Cleaning up messages older than {days} days")
    
    session = next(get_db_session())
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    deleted = (
        session.query(Notification)
        .filter(
            and_(
                Notification.is_read == True,
                Notification.read_at < cutoff,
            )
        )
        .delete()
    )
    
    session.commit()
    
    logger.info(f"Deleted {deleted} old messages")
    return {"deleted": deleted}


@shared_task(name="message.get_queue_stats")
def get_message_queue_stats() -> dict:
    """
    Get current queue statistics.
    
    Returns:
        dict with pending, processing, failed counts by priority
    """
    session = next(get_db_session())
    
    # Pending (not processed)
    pending_high = (
        session.query(Notification)
        .filter(
            and_(
                Notification.is_read == False,
                Notification.priority == NotificationPriority.HIGH,
            )
        )
        .count()
    )
    
    pending_normal = (
        session.query(Notification)
        .filter(
            and_(
                Notification.is_read == False,
                Notification.priority == NotificationPriority.NORMAL,
            )
        )
        .count()
    )
    
    pending_low = (
        session.query(Notification)
        .filter(
            and_(
                Notification.is_read == False,
                Notification.priority == NotificationPriority.LOW,
            )
        )
        .count()
    )
    
    # Recent completed (last hour)
    recent_completed = (
        session.query(Notification)
        .filter(
            and_(
                Notification.is_read == True,
                Notification.read_at >= datetime.utcnow() - timedelta(hours=1),
            )
        )
        .count()
    )
    
    return {
        "pending": {
            "high": pending_high,
            "normal": pending_normal,
            "low": pending_low,
            "total": pending_high + pending_normal + pending_low,
        },
        "recent_completed": recent_completed,
        "timestamp": datetime.utcnow().isoformat(),
    }


# =============================================================================
# Manual Trigger Tasks
# =============================================================================

@shared_task(
    name="message.process_single",
    bind=True,
)
def process_single_message(self, message_id: int) -> dict:
    """
    Manually trigger processing for a specific message.
    
    Args:
        message_id: ID of the message to process
    
    Returns:
        dict with processing result
    """
    logger.info(f"Manually processing message {message_id}")
    
    session = next(get_db_session())
    message = session.query(Notification).filter(Notification.id == message_id).first()
    
    if not message:
        return {"success": False, "error": "Message not found"}
    
    try:
        _process_notification(message, session)
        return {"success": True, "message_id": message_id}
    except Exception as e:
        logger.error(f"Failed to process message {message_id}: {e}")
        return {"success": False, "error": str(e)}


@shared_task(name="message.create_notification")
def create_notification(
    user_id: int,
    notification_type: str,
    title: str,
    message: str,
    priority: str = "normal",
    related_type: Optional[str] = None,
    related_id: Optional[int] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """
    Create a new notification and queue it for processing.
    
    Args:
        user_id: User to notify
        notification_type: Type of notification
        title: Notification title
        message: Notification message
        priority: Priority level (low, normal, high)
        related_type: Optional related entity type
        related_id: Optional related entity ID
        metadata: Optional additional metadata
    
    Returns:
        dict with created notification info
    """
    import json
    
    session = next(get_db_session())
    
    notification = Notification(
        user_id=user_id,
        type=NotificationType(notification_type),
        priority=NotificationPriority(priority),
        title=title,
        message=message,
        related_type=related_type,
        related_id=related_id,
        metadata=json.dumps(metadata or {}),
    )
    
    session.add(notification)
    session.commit()
    session.refresh(notification)
    
    logger.info(f"Created notification {notification.id} for user {user_id}")
    
    return {
        "success": True,
        "notification_id": notification.id,
        "type": notification_type,
        "priority": priority,
    }