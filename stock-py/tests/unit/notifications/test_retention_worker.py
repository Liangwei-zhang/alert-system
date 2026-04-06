import unittest

from apps.workers.retention.worker import RetentionMaintenanceWorker
from domains.notifications.retention_service import RetentionMaintenanceResult


class FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.closed = False

    async def commit(self) -> None:
        self.committed = True

    async def close(self) -> None:
        self.closed = True


class FakeRetentionService:
    def __init__(self, result: RetentionMaintenanceResult) -> None:
        self.result = result
        self.calls = 0

    async def run_once(self) -> RetentionMaintenanceResult:
        self.calls += 1
        return self.result


class StubRetentionMaintenanceWorker(RetentionMaintenanceWorker):
    def __init__(self, *, service: FakeRetentionService, session: FakeSession) -> None:
        super().__init__(poll_interval_seconds=60, drain_interval_seconds=5)
        self._service = service
        self._session = session

    async def open_session(self):
        return self._session

    def build_service(self, session):
        del session
        return self._service


class RetentionMaintenanceWorkerTest(unittest.IsolatedAsyncioTestCase):
    async def test_run_once_commits_and_closes_session(self) -> None:
        service = FakeRetentionService(
            RetentionMaintenanceResult(
                lock_acquired=True,
                message_outbox_deleted=3,
                message_receipts_archived=2,
                event_outbox_deleted=1,
            )
        )
        session = FakeSession()
        worker = StubRetentionMaintenanceWorker(service=service, session=session)

        result = await worker.run_once()

        self.assertEqual(
            result,
            {
                "lock_acquired": True,
                "message_outbox_deleted": 3,
                "message_receipts_archived": 2,
                "event_outbox_deleted": 1,
                "partition_archives_created": 0,
                "partition_rows_pruned": 0,
                "did_work": True,
            },
        )
        self.assertEqual(service.calls, 1)
        self.assertTrue(session.committed)
        self.assertTrue(session.closed)

    async def test_next_delay_seconds_prefers_drain_interval_when_work_was_done(self) -> None:
        worker = RetentionMaintenanceWorker(poll_interval_seconds=120, drain_interval_seconds=5)

        self.assertEqual(
            worker.next_delay_seconds(
                RetentionMaintenanceResult(lock_acquired=True, message_outbox_deleted=1)
            ),
            5,
        )
        self.assertEqual(
            worker.next_delay_seconds(RetentionMaintenanceResult(lock_acquired=False)),
            120,
        )
        self.assertEqual(
            worker.next_delay_seconds(RetentionMaintenanceResult(lock_acquired=True)),
            120,
        )


if __name__ == "__main__":
    unittest.main()
