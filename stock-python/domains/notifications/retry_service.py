"""
Retry service - Retry logic for failed notifications.
"""
import logging
import asyncio
from typing import Optional, Callable, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
import random

from domains.notifications.delivery_tracker import DeliveryStatus, DeliveryChannel, DeliveryTracker

logger = logging.getLogger(__name__)


class RetryStrategy(str, Enum):
    """Retry strategy enum."""
    FIXED = "fixed"           # Fixed interval between retries
    LINEAR = "linear"         # Linear backoff (1x, 2x, 3x...)
    EXPONENTIAL = "exponential"  # Exponential backoff (2, 4, 8, 16...)
    FIBONACCI = "fibonacci"    # Fibonacci backoff (1, 2, 3, 5, 8...)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3                 # Maximum number of retry attempts
    base_delay_seconds: float = 1.0      # Base delay for backoff
    max_delay_seconds: float = 60.0       # Maximum delay cap
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    retry_on_statuses: tuple = (DeliveryStatus.FAILED, DeliveryStatus.RETRYING)
    jitter: bool = True                  # Add randomness to delays


class RetryTask:
    """Task to be retried."""
    notification_id: int
    channel: DeliveryChannel
    attempt: int
    last_error: Optional[str]
    next_retry_at: datetime
    created_at: datetime

    def __init__(
        self,
        notification_id: int,
        channel: DeliveryChannel,
        attempt: int = 0,
        last_error: Optional[str] = None,
    ):
        self.notification_id = notification_id
        self.channel = channel
        self.attempt = attempt
        self.last_error = last_error
        self.next_retry_at = datetime.utcnow()
        self.created_at = datetime.utcnow()


class RetryService:
    """Service for retrying failed notifications."""

    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
        self._pending_tasks: dict[str, RetryTask] = {}  # "notification_id:channel" -> task
        self._retry_callback: Optional[Callable] = None
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

    def set_retry_callback(
        self,
        callback: Callable[[int, DeliveryChannel], Any],
    ) -> None:
        """Set callback for performing retry delivery."""
        self._retry_callback = callback

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number."""
        delay = self.config.base_delay_seconds

        if self.config.strategy == RetryStrategy.FIXED:
            pass  # delay stays as base

        elif self.config.strategy == RetryStrategy.LINEAR:
            delay = self.config.base_delay_seconds * (attempt + 1)

        elif self.config.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.config.base_delay_seconds * (2 ** attempt)

        elif self.config.strategy == RetryStrategy.FIBONACCI:
            # Fibonacci: 1, 1, 2, 3, 5, 8...
            fib = self._fibonacci(attempt + 1)
            delay = self.config.base_delay_seconds * fib

        # Apply cap
        delay = min(delay, self.config.max_delay_seconds)

        # Add jitter
        if self.config.jitter:
            jitter_range = delay * 0.3  # 30% jitter
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0, delay)  # Ensure non-negative

    def _fibonacci(self, n: int) -> int:
        """Calculate nth Fibonacci number."""
        if n <= 1:
            return 1
        a, b = 1, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return b

    def schedule_retry(
        self,
        notification_id: int,
        channel: DeliveryChannel,
        attempt: int = 0,
        last_error: Optional[str] = None,
    ) -> RetryTask:
        """Schedule a retry for a failed notification."""
        key = f"{notification_id}:{channel.value}"

        delay = self.calculate_delay(attempt)
        next_retry = datetime.utcnow() + timedelta(seconds=delay)

        task = RetryTask(
            notification_id=notification_id,
            channel=channel,
            attempt=attempt,
            last_error=last_error,
        )
        task.next_retry_at = next_retry

        self._pending_tasks[key] = task

        logger.info(
            f"Scheduled retry {attempt + 1}/{self.config.max_retries} for "
            f"notification {notification_id} on {channel.value} in {delay:.1f}s"
        )

        return task

    def cancel_retry(
        self,
        notification_id: int,
        channel: DeliveryChannel,
    ) -> bool:
        """Cancel a scheduled retry."""
        key = f"{notification_id}:{channel.value}"
        if key in self._pending_tasks:
            del self._pending_tasks[key]
            logger.info(f"Cancelled retry for notification {notification_id}")
            return True
        return False

    def get_pending_retries(self) -> list[RetryTask]:
        """Get all pending retry tasks sorted by next_retry_at."""
        return sorted(
            self._pending_tasks.values(),
            key=lambda t: t.next_retry_at
        )

    def get_ready_retries(self) -> list[RetryTask]:
        """Get all retries that are due to be executed."""
        now = datetime.utcnow()
        return [
            task for task in self._pending_tasks.values()
            if task.next_retry_at <= now
        ]

    async def process_ready_retries(self) -> list[tuple[RetryTask, bool]]:
        """Process all retries that are due."""
        results = []

        for task in self.get_ready_retries():
            success = await self._execute_retry(task)
            results.append((task, success))

        return results

    async def _execute_retry(self, task: RetryTask) -> bool:
        """Execute a single retry attempt."""
        if not self._retry_callback:
            logger.error("No retry callback configured")
            return False

        try:
            logger.info(
                f"Executing retry {task.attempt + 1}/{self.config.max_retries} for "
                f"notification {task.notification_id}"
            )

            result = await self._retry_callback(task.notification_id, task.channel)

            if result:
                # Success - remove from pending
                key = f"{task.notification_id}:{task.channel.value}"
                if key in self._pending_tasks:
                    del self._pending_tasks[key]
                logger.info(f"Retry succeeded for notification {task.notification_id}")
                return True
            else:
                # Retry failed - schedule next retry
                return self._schedule_next_retry(task, "Retry returned False")

        except Exception as e:
            logger.error(f"Retry failed with exception: {e}")
            return self._schedule_next_retry(task, str(e))

    def _schedule_next_retry(self, task: RetryTask, error: str) -> bool:
        """Schedule the next retry attempt."""
        next_attempt = task.attempt + 1

        if next_attempt >= self.config.max_retries:
            logger.warning(
                f"Max retries ({self.config.max_retries}) reached for "
                f"notification {task.notification_id}"
            )
            # Remove from pending
            key = f"{task.notification_id}:{task.channel.value}"
            if key in self._pending_tasks:
                del self._pending_tasks[key]
            return False

        # Schedule next retry
        self.schedule_retry(
            notification_id=task.notification_id,
            channel=task.channel,
            attempt=next_attempt,
            last_error=error,
        )

        return False

    async def start_worker(self, poll_interval_seconds: float = 5.0) -> None:
        """Start the background retry worker."""
        if self._running:
            logger.warning("Retry worker already running")
            return

        self._running = True

        async def worker():
            while self._running:
                try:
                    await self.process_ready_retries()
                except Exception as e:
                    logger.error(f"Error in retry worker: {e}")

                await asyncio.sleep(poll_interval_seconds)

        self._worker_task = asyncio.create_task(worker())
        logger.info("Retry worker started")

    async def stop_worker(self) -> None:
        """Stop the background retry worker."""
        self._running = False

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

        logger.info("Retry worker stopped")

    def get_status(self) -> dict:
        """Get status of retry service."""
        return {
            "running": self._running,
            "pending_count": len(self._pending_tasks),
            "pending_tasks": [
                {
                    "notification_id": task.notification_id,
                    "channel": task.channel.value,
                    "attempt": task.attempt,
                    "next_retry_at": task.next_retry_at.isoformat(),
                }
                for task in self._pending_tasks.values()
            ],
        }

    def load_from_failed_deliveries(
        self,
        failed_deliveries: list[DeliveryTracker],
    ) -> int:
        """Load pending retries from failed delivery records."""
        count = 0

        for record in failed_deliveries:
            # Skip if already at max retries
            if record.attempt >= self.config.max_retries:
                continue

            self.schedule_retry(
                notification_id=record.notification_id,
                channel=record.channel,
                attempt=record.attempt,
                last_error=record.error_message,
            )
            count += 1

        logger.info(f"Loaded {count} pending retries from failed deliveries")
        return count


# Global instance
retry_service = RetryService()