"""
Message worker - Process notification queue with Celery.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from celery import shared_task
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from infra.database import get_db_session
from domains.notifications.notification import Notification, NotificationType, NotificationPriority

logger = logging.getLogger(__name__)


class MessageStatus:
    """Message processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "failed"
    FAILED = "failed"
    RETRY = "retry"


class MessageWorker:
    """Worker for processing notification messages from queue."""

    def __init__(self, session: Optional[Session] = None):
        self._session = session

    @property
    def session(self) -> Session:
        """Get database session."""
        if self._session is None:
            self._session = next(get_db_session())
        return self._session

    def get_pending_messages(self, limit: int = 100) -> list[Notification]:
        """Get pending messages from the notification queue."""
        return (
            self.session.query(Notification)
            .filter(
                and_(
                    Notification.is_read == False,  # Not yet processed
                    Notification.priority != NotificationPriority.LOW,
                )
            )
            .order_by(
                Notification.priority.desc(),  # High priority first
                Notification.created_at.asc(),  # Oldest first
            )
            .limit(limit)
            .all()
        )

    def get_message_by_id(self, message_id: int) -> Optional[Notification]:
        """Get a specific message by ID."""
        return self.session.query(Notification).filter(
            Notification.id == message_id
        ).first()

    def mark_as_processing(self, message_id: int) -> bool:
        """Mark message as processing (for tracking)."""
        message = self.get_message_by_id(message_id)
        if message:
            # Store processing start time in metadata
            import json
            metadata = json.loads(message.metadata or "{}")
            metadata["processing_started_at"] = datetime.utcnow().isoformat()
            metadata["status"] = MessageStatus.PROCESSING
            message.metadata = json.dumps(metadata)
            self.session.commit()
            return True
        return False

    def mark_as_completed(self, message_id: int) -> bool:
        """Mark message as completed."""
        message = self.get_message_by_id(message_id)
        if message:
            message.is_read = True
            message.read_at = datetime.utcnow()
            
            import json
            metadata = json.loads(message.metadata or "{}")
            metadata["processed_at"] = datetime.utcnow().isoformat()
            metadata["status"] = MessageStatus.COMPLETED
            message.metadata = json.dumps(metadata)
            
            self.session.commit()
            return True
        return False

    def mark_as_failed(
        self, message_id: int, error: str, retry_count: int = 0
    ) -> bool:
        """Mark message as failed with error details."""
        message = self.get_message_by_id(message_id)
        if message:
            import json
            metadata = json.loads(message.metadata or "{}")
            metadata["status"] = MessageStatus.FAILED
            metadata["last_error"] = error
            metadata["last_error_at"] = datetime.utcnow().isoformat()
            metadata["retry_count"] = retry_count
            message.metadata = json.dumps(metadata)
            self.session.commit()
            return True
        return False

    def process_message(self, message_id: int) -> bool:
        """Process a single message."""
        message = self.get_message_by_id(message_id)
        if not message:
            logger.warning(f"Message {message_id} not found")
            return False

        try:
            self.mark_as_processing(message_id)
            
            # Process based on notification type
            if message.type == NotificationType.SIGNAL_BUY:
                self._handle_signal_notification(message, "buy")
            elif message.type == NotificationType.SIGNAL_SELL:
                self._handle_signal_notification(message, "sell")
            elif message.type == NotificationType.PRICE_ALERT:
                self._handle_price_alert(message)
            elif message.type == NotificationType.SYSTEM:
                self._handle_system_notification(message)
            else:
                logger.info(f"Unknown notification type: {message.type}")

            self.mark_as_completed(message_id)
            logger.info(f"Successfully processed message {message_id}")
            return True

        except Exception as e:
            logger.error(f"Error processing message {message_id}: {e}")
            import json
            metadata = json.loads(message.metadata or "{}")
            retry_count = metadata.get("retry_count", 0)
            self.mark_as_failed(message_id, str(e), retry_count)
            return False

    def _handle_signal_notification(self, message: Notification, signal_type: str):
        """Handle signal notification - queue email task."""
        # Import here to avoid circular imports
        from app.tasks.email_tasks import send_signal_email_task
        
        # Get related signal info from metadata
        import json
        metadata = json.loads(message.metadata or "{}")
        
        # Queue email task asynchronously
        send_signal_email_task.delay(
            user_id=message.user_id,
            signal_type=signal_type,
            symbol=metadata.get("symbol", "UNKNOWN"),
            price=metadata.get("price", 0.0),
            message_id=message.id,
        )

    def _handle_price_alert(self, message: Notification):
        """Handle price alert notification."""
        import json
        metadata = json.loads(message.metadata or "{}")
        
        # Queue email for price alert
        from app.tasks.email_tasks import send_price_alert_email_task
        
        send_price_alert_email_task.delay(
            user_id=message.user_id,
            symbol=metadata.get("symbol", "UNKNOWN"),
            current_price=metadata.get("current_price", 0.0),
            target_price=metadata.get("target_price", 0.0),
            message_id=message.id,
        )

    def _handle_system_notification(self, message: Notification):
        """Handle system notification."""
        logger.info(f"System notification: {message.title}")


# Celery task for processing message queue
@shared_task(
    name="message.process_queue",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=5,
)
def process_notification_queue(self, limit: int = 100):
    """
    Process pending notification messages from the queue.
    
    This task runs periodically to process notifications that need to be sent.
    """
    logger.info(f"Starting notification queue processing (limit: {limit})")
    
    worker = MessageWorker()
    messages = worker.get_pending_messages(limit)
    
    processed_count = 0
    failed_count = 0
    
    for message in messages:
        try:
            # Check if we should retry
            import json
            metadata = json.loads(message.metadata or "{}")
            retry_count = metadata.get("retry_count", 0)
            
            if retry_count >= 5:
                logger.warning(f"Message {message.id} exceeded max retries, skipping")
                failed_count += 1
                continue
            
            if worker.process_message(message.id):
                processed_count += 1
            else:
                failed_count += 1
                
        except Exception as e:
            logger.error(f"Error processing message {message.id}: {e}")
            failed_count += 1

    logger.info(
        f"Queue processing complete: {processed_count} processed, {failed_count} failed"
    )
    return {
        "processed": processed_count,
        "failed": failed_count,
        "total": len(messages),
    }


@shared_task(
    name="message.retry_failed",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def retry_failed_messages(self, max_age_minutes: int = 30, limit: int = 50):
    """
    Retry failed messages that are older than specified minutes.
    
    This task runs periodically to retry messages that previously failed.
    """
    logger.info(f"Retrying failed messages (max_age: {max_age_minutes} min)")
    
    cutoff_time = datetime.utcnow() - timedelta(minutes=max_age_minutes)
    
    # Query failed messages
    failed_messages = (
        get_db_session()
        .query(Notification)
        .filter(
            and_(
                Notification.is_read == True,  # Previously marked as read/failed
                Notification.read_at >= cutoff_time,
            )
        )
        .limit(limit)
        .all()
    )
    
    worker = MessageWorker()
    retried_count = 0
    
    for message in failed_messages:
        try:
            import json
            metadata = json.loads(message.metadata or "{}")
            
            if metadata.get("status") == MessageStatus.FAILED:
                # Reset for retry
                message.is_read = False
                message.read_at = None
                metadata["status"] = MessageStatus.RETRY
                metadata["retryAttemptedAt"] = datetime.utcnow().isoformat()
                message.metadata = json.dumps(metadata)
                message.save()
                
                # Process again
                worker.process_message(message.id)
                retried_count += 1
                
        except Exception as e:
            logger.error(f"Error retrying message {message.id}: {e}")

    logger.info(f"Retry complete: {retried_count} messages retried")
    return {"retried": retried_count}


@shared_task(name="message.cleanup")
def cleanup_old_messages(days: int = 30):
    """
    Clean up old processed notifications.
    
    Args:
        days: Number of days to keep messages (default: 30)
    """
    logger.info(f"Cleaning up messages older than {days} days")
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Delete old processed notifications
    session = next(get_db_session())
    deleted = (
        session.query(Notification)
        .filter(
            and_(
                Notification.is_read == True,
                Notification.read_at < cutoff_date,
            )
        )
        .delete()
    )
    session.commit()
    
    logger.info(f"Deleted {deleted} old messages")
    return {"deleted": deleted}