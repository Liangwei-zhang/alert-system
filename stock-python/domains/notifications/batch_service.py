"""
Batch service - Notification batching for efficiency.
"""
import logging
import asyncio
from typing import Any, Callable, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


@dataclass
class BatchConfig:
    """Configuration for notification batching."""
    max_batch_size: int = 50           # Max notifications per batch
    max_wait_time_ms: int = 5000       # Max wait time before flush (ms)
    flush_on_full: bool = True         # Flush immediately when batch is full
    enable_deduplication: bool = True  # Deduplicate similar notifications
    dedupe_window_seconds: int = 300  # Dedupe window for similar notifications


@dataclass
class NotificationBatch:
    """A batch of notifications to be sent together."""
    id: str
    notifications: list[dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    flushed_at: Optional[datetime] = None
    user_id: Optional[int] = None

    def add(self, notification: dict) -> None:
        """Add a notification to the batch."""
        self.notifications.append(notification)

    def is_full(self, max_size: int) -> bool:
        """Check if batch is full."""
        return len(self.notifications) >= max_size

    def to_dict(self) -> dict:
        """Convert batch to dictionary."""
        return {
            "id": self.id,
            "notifications": self.notifications,
            "count": len(self.notifications),
            "created_at": self.created_at.isoformat(),
            "flushed_at": self.flushed_at.isoformat() if self.flushed_at else None,
            "user_id": self.user_id,
        }


class DeduplicationCache:
    """Cache for deduplicating similar notifications."""

    def __init__(self, window_seconds: int = 300):
        self._cache: dict[str, datetime] = {}
        self._window = timedelta(seconds=window_seconds)

    def _make_key(self, notification: dict) -> str:
        """Create deduplication key from notification."""
        # Use type, user_id, related_type, related_id for deduplication
        key_parts = [
            str(notification.get("type", "")),
            str(notification.get("user_id", "")),
            str(notification.get("related_type", "")),
            str(notification.get("related_id", "")),
        ]
        return ":".join(key_parts)

    def is_duplicate(self, notification: dict) -> bool:
        """Check if notification is a duplicate."""
        key = self._make_key(notification)
        if key not in self._cache:
            return False

        # Check if within window
        cached_time = self._cache[key]
        if datetime.utcnow() - cached_time > self._window:
            del self._cache[key]
            return False

        return True

    def add(self, notification: dict) -> None:
        """Add notification to cache."""
        key = self._make_key(notification)
        self._cache[key] = datetime.utcnow()

    def cleanup(self) -> None:
        """Remove expired entries."""
        now = datetime.utcnow()
        expired = [k for k, v in self._cache.items() if now - v > self._window]
        for k in expired:
            del self._cache[k]


class BatchService:
    """Service for batching notifications."""

    def __init__(self, config: BatchConfig = None):
        self.config = config or BatchConfig()
        self._batches: dict[str, NotificationBatch] = {}  # user_id -> batch
        self._dedup_cache = DeduplicationCache(self.config.dedupe_window_seconds)
        self._flush_callback: Optional[Callable] = None
        self._timers: dict[str, asyncio.Task] = {}

    def set_flush_callback(self, callback: Callable[[NotificationBatch], Any]) -> None:
        """Set callback for when a batch is flushed."""
        self._flush_callback = callback

    async def add(
        self,
        notification: dict,
        user_id: int,
    ) -> Optional[NotificationBatch]:
        """
        Add a notification to the batch queue.
        
        Returns the batch if it was flushed, None otherwise.
        """
        # Check deduplication
        if self.config.enable_deduplication:
            if self._dedup_cache.is_duplicate(notification):
                logger.debug(f"Skipping duplicate notification: {notification.get('type')}")
                return None
            self._dedup_cache.add(notification)

        # Get or create batch for user
        user_id_str = str(user_id)
        if user_id_str not in self._batches:
            self._batches[user_id_str] = NotificationBatch(
                id=f"batch_{user_id_str}_{datetime.utcnow().timestamp()}",
                user_id=user_id,
            )

        batch = self._batches[user_id_str]
        batch.add(notification)

        # Check if should flush
        flushed = None
        if batch.is_full(self.config.max_batch_size):
            flushed = await self._flush_batch(user_id_str)
        elif self.config.flush_on_full:
            # Start timer if not already started
            if user_id_str not in self._timers:
                self._start_flush_timer(user_id_str)

        return flushed

    def _start_flush_timer(self, user_id_str: str) -> None:
        """Start a timer to flush the batch after max_wait_time."""
        async def timer_callback():
            await asyncio.sleep(self.config.max_wait_time_ms / 1000)
            await self._flush_batch(user_id_str)

        self._timers[user_id_str] = asyncio.create_task(timer_callback())

    async def _flush_batch(self, user_id_str: str) -> Optional[NotificationBatch]:
        """Flush a batch and send it."""
        batch = self._batches.get(user_id_str)
        if not batch or not batch.notifications:
            return None

        # Cancel timer if exists
        if user_id_str in self._timers:
            self._timers[user_id_str].cancel()
            del self._timers[user_id_str]

        batch.flushed_at = datetime.utcnow()

        logger.info(f"Flushing batch {batch.id} with {len(batch.notifications)} notifications")

        # Call the flush callback
        if self._flush_callback:
            try:
                await self._flush_callback(batch)
            except Exception as e:
                logger.error(f"Error in flush callback: {e}")

        # Remove batch
        del self._batches[user_id_str]

        return batch

    async def flush_all(self) -> list[NotificationBatch]:
        """Flush all pending batches."""
        flushed = []
        user_ids = list(self._batches.keys())

        for user_id_str in user_ids:
            batch = await self._flush_batch(user_id_str)
            if batch:
                flushed.append(batch)

        return flushed

    async def flush_user(self, user_id: int) -> Optional[NotificationBatch]:
        """Flush a specific user's batch."""
        return await self._flush_batch(str(user_id))

    def get_pending_count(self, user_id: int = None) -> int:
        """Get count of pending notifications."""
        if user_id is not None:
            batch = self._batches.get(str(user_id))
            return len(batch.notifications) if batch else 0

        return sum(len(b.notifications) for b in self._batches.values())

    def get_batch_status(self) -> dict:
        """Get status of all batches."""
        return {
            "batch_count": len(self._batches),
            "total_pending": sum(len(b.notifications) for b in self._batches.values()),
            "batches": {
                user_id: {
                    "count": len(batch.notifications),
                    "created_at": batch.created_at.isoformat(),
                }
                for user_id, batch in self._batches.items()
            },
        }

    def cleanup_expired(self) -> None:
        """Cleanup expired entries from deduplication cache."""
        self._dedup_cache.cleanup()


# Global instance
batch_service = BatchService()