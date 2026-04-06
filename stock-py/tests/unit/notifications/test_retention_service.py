import unittest

from domains.notifications.partition_archive_service import PartitionArchiveOutcome
from domains.notifications.retention_service import (
    RetentionMaintenanceResult,
    RetentionMaintenanceService,
)


class FakeLockManager:
    def __init__(self, *, acquired: bool = True) -> None:
        self.acquired = acquired
        self.acquire_calls = 0
        self.release_calls = 0

    async def acquire(self) -> bool:
        self.acquire_calls += 1
        return self.acquired

    async def release(self) -> None:
        self.release_calls += 1


class FakeReceiptRepository:
    def __init__(self, counts) -> None:
        self.counts = list(counts)
        self.calls = []

    async def archive_terminal_receipts(self, *, retention_days: int, limit: int) -> int:
        self.calls.append({"retention_days": retention_days, "limit": limit})
        if not self.counts:
            return 0
        return self.counts.pop(0)


class FakeOutboxRepository:
    def __init__(self, counts) -> None:
        self.counts = list(counts)
        self.calls = []

    async def delete_terminal_messages(self, *, retention_days: int, limit: int) -> int:
        self.calls.append({"retention_days": retention_days, "limit": limit})
        if not self.counts:
            return 0
        return self.counts.pop(0)


class FakeEventOutboxRepository:
    def __init__(self, counts) -> None:
        self.counts = list(counts)
        self.calls = []

    async def delete_published(self, *, retention_days: int, limit: int) -> int:
        self.calls.append({"retention_days": retention_days, "limit": limit})
        if not self.counts:
            return 0
        return self.counts.pop(0)


class FakePartitionArchiveService:
    def __init__(self, outcome: PartitionArchiveOutcome | None = None) -> None:
        self.outcome = outcome or PartitionArchiveOutcome()
        self.calls = 0

    async def archive_expired_partitions(self) -> PartitionArchiveOutcome:
        self.calls += 1
        return self.outcome


class RetentionMaintenanceServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_run_once_returns_empty_result_when_lock_not_acquired(self) -> None:
        lock_manager = FakeLockManager(acquired=False)
        service = RetentionMaintenanceService(
            object(),
            lock_manager=lock_manager,
            receipt_repository=FakeReceiptRepository([5]),
            outbox_repository=FakeOutboxRepository([5]),
            event_outbox_repository=FakeEventOutboxRepository([5]),
            partition_archive_service=FakePartitionArchiveService(),
            batch_size=2,
        )

        result = await service.run_once()

        self.assertEqual(result, RetentionMaintenanceResult(lock_acquired=False))
        self.assertEqual(lock_manager.acquire_calls, 1)
        self.assertEqual(lock_manager.release_calls, 0)

    async def test_run_once_drains_batches_until_counts_drop_below_batch_size(self) -> None:
        lock_manager = FakeLockManager()
        receipt_repository = FakeReceiptRepository([2, 1])
        outbox_repository = FakeOutboxRepository([2, 2, 0])
        event_outbox_repository = FakeEventOutboxRepository([2, 1])
        service = RetentionMaintenanceService(
            object(),
            lock_manager=lock_manager,
            receipt_repository=receipt_repository,
            outbox_repository=outbox_repository,
            event_outbox_repository=event_outbox_repository,
            partition_archive_service=FakePartitionArchiveService(),
            batch_size=2,
            message_outbox_retention_days=30,
            message_receipt_archive_days=60,
            event_outbox_retention_days=14,
        )

        result = await service.run_once()

        self.assertEqual(
            result,
            RetentionMaintenanceResult(
                lock_acquired=True,
                message_outbox_deleted=4,
                message_receipts_archived=3,
                event_outbox_deleted=3,
                partition_archives_created=0,
                partition_rows_pruned=0,
            ),
        )
        self.assertEqual(lock_manager.acquire_calls, 1)
        self.assertEqual(lock_manager.release_calls, 1)
        self.assertEqual(
            receipt_repository.calls,
            [
                {"retention_days": 60, "limit": 2},
                {"retention_days": 60, "limit": 2},
            ],
        )
        self.assertEqual(
            outbox_repository.calls,
            [
                {"retention_days": 30, "limit": 2},
                {"retention_days": 30, "limit": 2},
                {"retention_days": 30, "limit": 2},
            ],
        )
        self.assertEqual(
            event_outbox_repository.calls,
            [
                {"retention_days": 14, "limit": 2},
                {"retention_days": 14, "limit": 2},
            ],
        )

    async def test_run_once_skips_receipt_archiving_when_disabled(self) -> None:
        receipt_repository = FakeReceiptRepository([2])
        service = RetentionMaintenanceService(
            object(),
            lock_manager=FakeLockManager(),
            receipt_repository=receipt_repository,
            outbox_repository=FakeOutboxRepository([0]),
            event_outbox_repository=FakeEventOutboxRepository([0]),
            partition_archive_service=FakePartitionArchiveService(),
            batch_size=5,
            message_receipt_archive_days=0,
        )

        result = await service.run_once()

        self.assertEqual(result.message_receipts_archived, 0)
        self.assertEqual(receipt_repository.calls, [])

    async def test_run_once_includes_partition_archive_counts(self) -> None:
        archive_service = FakePartitionArchiveService(
            PartitionArchiveOutcome(partitions_archived=2, rows_pruned=120)
        )
        service = RetentionMaintenanceService(
            object(),
            lock_manager=FakeLockManager(),
            receipt_repository=FakeReceiptRepository([0]),
            outbox_repository=FakeOutboxRepository([0]),
            event_outbox_repository=FakeEventOutboxRepository([0]),
            partition_archive_service=archive_service,
            batch_size=10,
        )

        result = await service.run_once()

        self.assertEqual(result.partition_archives_created, 2)
        self.assertEqual(result.partition_rows_pruned, 120)
        self.assertTrue(result.did_work)
        self.assertEqual(archive_service.calls, 1)


if __name__ == "__main__":
    unittest.main()
