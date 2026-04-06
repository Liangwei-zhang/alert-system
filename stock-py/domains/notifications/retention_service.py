from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from domains.notifications.partition_archive_service import (
    NotificationPartitionArchiveService,
    PartitionArchiveOutcome,
)
from domains.notifications.repository import MessageOutboxRepository, ReceiptRepository
from infra.core.config import Settings, get_settings
from infra.events.outbox import EventOutboxRepository

MAX_RETENTION_PASSES = 20


@dataclass(slots=True)
class RetentionMaintenanceResult:
    lock_acquired: bool
    message_outbox_deleted: int = 0
    message_receipts_archived: int = 0
    event_outbox_deleted: int = 0
    partition_archives_created: int = 0
    partition_rows_pruned: int = 0

    @property
    def did_work(self) -> bool:
        return any(
            (
                self.message_outbox_deleted,
                self.message_receipts_archived,
                self.event_outbox_deleted,
                self.partition_archives_created,
                self.partition_rows_pruned,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["did_work"] = self.did_work
        return payload


class RetentionLockManager(Protocol):
    async def acquire(self) -> bool: ...

    async def release(self) -> None: ...


class PgAdvisoryRetentionLock:
    def __init__(self, session: AsyncSession, key: int) -> None:
        self.session = session
        self.key = int(key)
        self._acquired = False
        self._uses_advisory_lock = True

    async def acquire(self) -> bool:
        bind = getattr(self.session, "bind", None)
        dialect_name = getattr(getattr(bind, "dialect", None), "name", None)
        if dialect_name is not None and dialect_name != "postgresql":
            self._acquired = True
            self._uses_advisory_lock = False
            return True

        result = await self.session.execute(
            text("SELECT pg_try_advisory_lock(:key) AS acquired"),
            {"key": self.key},
        )
        row = result.first()
        self._acquired = bool(row[0]) if row is not None else False
        return self._acquired

    async def release(self) -> None:
        if not self._acquired:
            return
        if self._uses_advisory_lock:
            await self.session.execute(
                text("SELECT pg_advisory_unlock(:key)"),
                {"key": self.key},
            )
        self._acquired = False


class RetentionMaintenanceService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
        receipt_repository: ReceiptRepository | None = None,
        outbox_repository: MessageOutboxRepository | None = None,
        event_outbox_repository: EventOutboxRepository | None = None,
        lock_manager: RetentionLockManager | None = None,
        partition_archive_service: NotificationPartitionArchiveService | None = None,
        batch_size: int | None = None,
        max_passes: int = MAX_RETENTION_PASSES,
        message_outbox_retention_days: int | None = None,
        message_receipt_archive_days: int | None = None,
        event_outbox_retention_days: int | None = None,
        partition_archive_enabled: bool | None = None,
    ) -> None:
        app_settings = settings or get_settings()
        self.session = session
        self.receipt_repository = receipt_repository or ReceiptRepository(session)
        self.outbox_repository = outbox_repository or MessageOutboxRepository(session)
        self.event_outbox_repository = event_outbox_repository or EventOutboxRepository(session)
        self.lock_manager = lock_manager or PgAdvisoryRetentionLock(
            session,
            app_settings.retention_advisory_lock_key,
        )
        self.batch_size = max(
            1,
            int(app_settings.retention_cleanup_batch_size if batch_size is None else batch_size),
        )
        self.max_passes = max(1, int(max_passes))
        self.partition_archive_enabled = (
            app_settings.retention_partition_archive_enabled
            if partition_archive_enabled is None
            else bool(partition_archive_enabled)
        )
        self.partition_archive_service = partition_archive_service or (
            NotificationPartitionArchiveService(session, settings=app_settings)
            if self.partition_archive_enabled
            else None
        )
        self.message_outbox_retention_days = max(
            1,
            int(
                app_settings.retention_message_outbox_retention_days
                if message_outbox_retention_days is None
                else message_outbox_retention_days
            ),
        )
        self.message_receipt_archive_days = max(
            0,
            int(
                app_settings.retention_message_receipt_archive_days
                if message_receipt_archive_days is None
                else message_receipt_archive_days
            ),
        )
        self.event_outbox_retention_days = max(
            1,
            int(
                app_settings.retention_event_outbox_retention_days
                if event_outbox_retention_days is None
                else event_outbox_retention_days
            ),
        )

    async def run_once(self) -> RetentionMaintenanceResult:
        if not await self.lock_manager.acquire():
            return RetentionMaintenanceResult(lock_acquired=False)

        try:
            message_receipts_archived = 0
            if self.message_receipt_archive_days > 0:
                message_receipts_archived = await self._drain_batches(
                    self.receipt_repository.archive_terminal_receipts,
                    retention_days=self.message_receipt_archive_days,
                )

            partition_archive_outcome = PartitionArchiveOutcome()
            if self.partition_archive_enabled and self.partition_archive_service is not None:
                partition_archive_outcome = (
                    await self.partition_archive_service.archive_expired_partitions()
                )

            message_outbox_deleted = await self._drain_batches(
                self.outbox_repository.delete_terminal_messages,
                retention_days=self.message_outbox_retention_days,
            )
            event_outbox_deleted = await self._drain_batches(
                self.event_outbox_repository.delete_published,
                retention_days=self.event_outbox_retention_days,
            )
            return RetentionMaintenanceResult(
                lock_acquired=True,
                message_outbox_deleted=message_outbox_deleted,
                message_receipts_archived=message_receipts_archived,
                event_outbox_deleted=event_outbox_deleted,
                partition_archives_created=partition_archive_outcome.partitions_archived,
                partition_rows_pruned=partition_archive_outcome.rows_pruned,
            )
        finally:
            await self.lock_manager.release()

    async def _drain_batches(self, operation, *, retention_days: int) -> int:
        total = 0
        for _ in range(self.max_passes):
            processed = await operation(retention_days=retention_days, limit=self.batch_size)
            total += int(processed or 0)
            if processed < self.batch_size:
                break
        return total
