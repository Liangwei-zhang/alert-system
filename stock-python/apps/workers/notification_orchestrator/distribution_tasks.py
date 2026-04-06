"""
Distribution tasks - Celery tasks for message distribution processing.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from celery import shared_task
from sqlalchemy import and_, or_, select, update, func

from infra.database import get_db_session
from domains.notifications.distribution import (
    MessageQueue,
    DeliveryReceipt,
    ArchivedMessage,
    DistributionStatus,
    DistributionPriority,
    DeliveryReceiptStatus,
)
from domains.notifications.distribution_service import DistributionService

logger = logging.getLogger(__name__)


# =============================================================================
# Queue Processing Tasks
# =============================================================================

@shared_task(
    name="distribution.process_high_priority",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def process_high_priority_queue(self, limit: int = 50) -> dict:
    """
    Process high and urgent priority messages immediately.
    """
    logger.info(f"Processing high priority queue (limit: {limit})")
    
    session = next(get_db_session())
    service = DistributionService(session)
    
    messages = session.query(MessageQueue).filter(
        and_(
            MessageQueue.status == DistributionStatus.PENDING,
            MessageQueue.priority.in_([DistributionPriority.HIGH, DistributionPriority.URGENT]),
            or_(
                MessageQueue.scheduled_at.is_(None),
                MessageQueue.scheduled_at <= datetime.utcnow()
            )
        )
    ).order_by(
        MessageQueue.priority.desc(),
        MessageQueue.created_at.asc()
    ).limit(limit).all()
    
    processed = 0
    failed = 0
    
    for message in messages:
        try:
            _process_queue_message(message, service, session)
            processed += 1
        except Exception as e:
            logger.error(f"Failed to process queue {message.id}: {e}")
            failed += 1
    
    session.close()
    logger.info(f"High priority processing: {processed} done, {failed} failed")
    return {"processed": processed, "failed": failed, "total": len(messages)}


@shared_task(
    name="distribution.process_normal_priority",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def process_normal_priority_queue(self, limit: int = 100) -> dict:
    """
    Process normal and low priority messages.
    """
    logger.info(f"Processing normal priority queue (limit: {limit})")
    
    session = next(get_db_session())
    service = DistributionService(session)
    
    messages = session.query(MessageQueue).filter(
        and_(
            MessageQueue.status == DistributionStatus.PENDING,
            MessageQueue.priority.in_([DistributionPriority.NORMAL, DistributionPriority.LOW]),
            or_(
                MessageQueue.scheduled_at.is_(None),
                MessageQueue.scheduled_at <= datetime.utcnow()
            )
        )
    ).order_by(
        MessageQueue.priority.desc(),
        MessageQueue.created_at.asc()
    ).limit(limit).all()
    
    processed = 0
    failed = 0
    
    for message in messages:
        try:
            _process_queue_message(message, service, session)
            processed += 1
        except Exception as e:
            logger.error(f"Failed to process queue {message.id}: {e}")
            failed += 1
    
    session.close()
    logger.info(f"Normal priority processing: {processed} done, {failed} failed")
    return {"processed": processed, "failed": failed, "total": len(messages)}


@shared_task(
    name="distribution.process_single",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def process_single_queue_message(self, queue_id: int) -> dict:
    """
    Process a single queue message by ID.
    """
    logger.info(f"Processing single queue message {queue_id}")
    
    session = next(get_db_session())
    service = DistributionService(session)
    
    message = session.query(MessageQueue).filter(
        MessageQueue.id == queue_id
    ).first()
    
    if not message:
        session.close()
        return {"success": False, "error": "Message not found"}
    
    try:
        _process_queue_message(message, service, session)
        session.close()
        return {"success": True, "queue_id": queue_id}
    except Exception as e:
        logger.error(f"Failed to process queue {queue_id}: {e}")
        session.close()
        return {"success": False, "error": str(e)}


def _process_queue_message(queue: MessageQueue, service: DistributionService, session) -> bool:
    """
    Process a single queue message based on its channel.
    """
    # Mark as processing
    service.mark_processing(queue.id)
    
    channel = queue.channel
    success = False
    
    if channel == "email":
        success = _deliver_via_email(queue, session)
    elif channel == "push":
        success = _deliver_via_push(queue, session)
    elif channel == "in_app":
        success = _deliver_via_in_app(queue, session)
    elif channel == "webhook":
        success = _deliver_via_webhook(queue, session)
    elif channel == "sms":
        success = _deliver_via_sms(queue, session)
    else:
        logger.warning(f"Unknown channel: {channel}")
        service.mark_failed(queue.id, f"Unknown channel: {channel}")
        return False
    
    if success:
        service.mark_delivered(queue.id)
        logger.info(f"Delivered queue {queue.id} via {channel}")
    else:
        service.mark_failed(queue.id, "Delivery failed")
        logger.error(f"Failed to deliver queue {queue.id}")
    
    return success


def _deliver_via_email(queue: MessageQueue, session) -> bool:
    """Deliver message via email."""
    from app.tasks.email_tasks import send_notification_email_task
    
    try:
        # Queue email task
        send_notification_email_task.delay(
            user_id=queue.user_id,
            subject=queue.title,
            body=queue.message,
            queue_id=queue.id,
        )
        
        # Create pending receipt
        receipt = DeliveryReceipt(
            queue_id=queue.id,
            status=DeliveryReceiptStatus.SENT,
            sent_at=datetime.utcnow(),
        )
        session.add(receipt)
        session.commit()
        
        return True
    except Exception as e:
        logger.error(f"Email delivery failed: {e}")
        return False


def _deliver_via_push(queue: MessageQueue, session) -> bool:
    """Deliver message via push notification."""
    from app.tasks.worker_tasks import send_push_notification_task
    
    try:
        metadata = json.loads(queue.metadata or "{}")
        
        send_push_notification_task.delay(
            user_id=queue.user_id,
            title=queue.title,
            body=queue.message,
            data=metadata,
            queue_id=queue.id,
        )
        
        receipt = DeliveryReceipt(
            queue_id=queue.id,
            status=DeliveryReceiptStatus.SENT,
            sent_at=datetime.utcnow(),
        )
        session.add(receipt)
        session.commit()
        
        return True
    except Exception as e:
        logger.error(f"Push delivery failed: {e}")
        return False


def _deliver_via_in_app(queue: MessageQueue, session) -> bool:
    """Deliver message as in-app notification."""
    from domains.notifications.notification import Notification, NotificationPriority, NotificationType
    
    try:
        # Create in-app notification
        notification = Notification(
            user_id=queue.user_id,
            type=NotificationType.SYSTEM,
            priority=NotificationPriority.NORMAL,
            title=queue.title,
            message=queue.message,
            related_type="distribution",
            related_id=queue.id,
        )
        session.add(notification)
        session.commit()
        
        receipt = DeliveryReceipt(
            queue_id=queue.id,
            status=DeliveryReceiptStatus.DELIVERED,
            sent_at=datetime.utcnow(),
            delivered_at=datetime.utcnow(),
        )
        session.add(receipt)
        session.commit()
        
        return True
    except Exception as e:
        logger.error(f"In-app delivery failed: {e}")
        return False


def _deliver_via_webhook(queue: MessageQueue, session) -> bool:
    """Deliver message via webhook."""
    import requests
    
    try:
        metadata = json.loads(queue.metadata or "{}")
        webhook_url = metadata.get("webhook_url")
        
        if not webhook_url:
            raise ValueError("No webhook_url in metadata")
        
        payload = {
            "title": queue.title,
            "message": queue.message,
            "user_id": queue.user_id,
            "queue_id": queue.id,
            "metadata": metadata,
        }
        
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=30,
            headers={"Content-Type": "application/json"}
        )
        
        channel_delivery_id = response.headers.get("X-Message-ID") if response.headers.get("X-Message-ID") else None
        
        receipt = DeliveryReceipt(
            queue_id=queue.id,
            channel_delivery_id=channel_delivery_id,
            status=DeliveryReceiptStatus.SENT,
            sent_at=datetime.utcnow(),
            channel_response=json.dumps({"status_code": response.status_code}),
        )
        session.add(receipt)
        session.commit()
        
        return response.ok
    except Exception as e:
        logger.error(f"Webhook delivery failed: {e}")
        return False


def _deliver_via_sms(queue: MessageQueue, session) -> bool:
    """Deliver message via SMS."""
    # Placeholder for SMS integration
    logger.warning("SMS delivery not implemented")
    return False


# =============================================================================
# Escalation Tasks
# =============================================================================

@shared_task(name="distribution.escalate_failed")
def escalate_failed_messages(max_age_hours: int = 24) -> dict:
    """
    Escalate failed messages that are old enough for attention.
    """
    logger.info(f"Escalating failed messages older than {max_age_hours} hours")
    
    session = next(get_db_session())
    service = DistributionService(session)
    
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    
    messages = session.query(MessageQueue).filter(
        and_(
            MessageQueue.status == DistributionStatus.FAILED,
            MessageQueue.updated_at < cutoff,
            MessageQueue.escalation_level < 3,
        )
    ).all()
    
    escalated = 0
    
    for message in messages:
        service.escalate_message(
            message.id,
            note=f"Auto-escalated after {max_age_hours}h of failure"
        )
        escalated += 1
    
    session.close()
    logger.info(f"Escalated {escalated} failed messages")
    return {"escalated": escalated}


@shared_task(name="distribution.check_escalations")
def review_escalated_messages() -> dict:
    """
    Review escalated messages and check if they need further action.
    """
    logger.info("Reviewing escalated messages")
    
    session = next(get_db_session())
    service = DistributionService(session)
    
    escalated = service.get_escalated_messages(limit=100)
    
    # Just return count - manual intervention needed
    session.close()
    return {"escalated_count": len(escalated)}


# =============================================================================
# Archiving Tasks
# =============================================================================

@shared_task(name="distribution.archive_completed")
def archive_old_completed_messages(days: int = 30, limit: int = 1000) -> dict:
    """
    Archive old completed messages.
    """
    logger.info(f"Archiving completed messages older than {days} days")
    
    session = next(get_db_session())
    service = DistributionService(session)
    
    count = service.archive_completed(days_old=days, limit=limit)
    
    session.close()
    return {"archived": count}


@shared_task(name="distribution.archive_failed")
def archive_failed_messages(limit: int = 500) -> dict:
    """
    Archive messages that exceeded max retries.
    """
    logger.info("Archiving failed messages with max retries")
    
    session = next(get_db_session())
    service = DistributionService(session)
    
    count = service.archive_failed_max_retries(limit=limit)
    
    session.close()
    return {"archived": count}


@shared_task(name="distribution.cleanup_archived")
def cleanup_old_archives(days: int = 365, limit: int = 10000) -> dict:
    """
    Permanently delete old archived messages.
    """
    logger.info(f"Cleaning up archives older than {days} days")
    
    session = next(get_db_session())
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    deleted = session.query(ArchivedMessage).filter(
        ArchivedMessage.archived_at < cutoff
    ).delete()
    
    session.commit()
    session.close()
    
    logger.info(f"Deleted {deleted} archived messages")
    return {"deleted": deleted}


# =============================================================================
# Queue Management Tasks
# =============================================================================

@shared_task(name="distribution.get_stats")
def get_queue_stats() -> dict:
    """
    Get current queue statistics.
    """
    session = next(get_db_session())
    service = DistributionService(session)
    
    stats = service.get_queue_stats()
    
    session.close()
    return stats


@shared_task(name="distribution.retry_pending")
def retry_pending_messages(max_retries: int = 3) -> dict:
    """
    Retry messages that are still pending but stuck in processing.
    """
    logger.info("Retrying stuck pending messages")
    
    session = next(get_db_session())
    
    # Find messages stuck in processing for too long
    cutoff = datetime.utcnow() - timedelta(hours=1)
    
    stuck = session.query(MessageQueue).filter(
        and_(
            MessageQueue.status == DistributionStatus.PROCESSING,
            MessageQueue.processed_at < cutoff,
        )
    ).all()
    
    retried = 0
    for message in stuck:
        message.status = DistributionStatus.PENDING
        message.retry_count += 1
        retried += 1
    
    session.commit()
    session.close()
    
    logger.info(f"Reset {retried} stuck messages to pending")
    return {"retried": retried}


@shared_task(name="distribution.create_queue_message")
def create_queue_message(
    user_id: int,
    title: str,
    message: str,
    channel: str = "in_app",
    priority: str = "normal",
    notification_id: Optional[int] = None,
    metadata: Optional[dict] = None,
    scheduled_at: Optional[datetime] = None,
) -> dict:
    """
    Create a new queue message.
    """
    session = next(get_db_session())
    service = DistributionService(session)
    
    queue = service.enqueue_message(
        user_id=user_id,
        title=title,
        message=message,
        channel=channel,
        priority=DistributionPriority(priority),
        notification_id=notification_id,
        metadata=metadata,
        scheduled_at=scheduled_at,
    )
    
    session.close()
    
    return {
        "success": True,
        "queue_id": queue.id,
        "priority": priority,
    }


@shared_task(name="distribution.schedule_from_notification")
def queue_from_notification(
    notification_id: int,
    channel: str = "email",
    priority: str = "normal",
) -> dict:
    """
    Create queue messages for all users who should receive a notification.
    """
    from domains.notifications.notification import Notification
    
    logger.info(f"Creating queue messages for notification {notification_id}")
    
    session = next(get_db_session())
    service = DistributionService(session)
    
    notification = session.query(Notification).filter(
        Notification.id == notification_id
    ).first()
    
    if not notification:
        session.close()
        return {"success": False, "error": "Notification not found"}
    
    # Get user device preferences to determine channels
    # This is a simplified version - real implementation would check user preferences
    queue = service.enqueue_message(
        user_id=notification.user_id,
        title=notification.title,
        message=notification.message,
        channel=channel,
        priority=DistributionPriority(priority),
        notification_id=notification_id,
        metadata=json.loads(notification.metadata or "{}") if notification.metadata else None,
    )
    
    session.close()
    
    return {
        "success": True,
        "queue_id": queue.id,
    }


# =============================================================================
# Periodic Task Configuration
# =============================================================================

# These would be configured in Celery beat for scheduled execution:
# - distribution.process_high_priority -> every 1 minute
# - distribution.process_normal_priority -> every 5 minutes
# - distribution.escalate_failed -> every hour
# - distribution.archive_completed -> daily
# - distribution.retry_pending -> every 5 minutes