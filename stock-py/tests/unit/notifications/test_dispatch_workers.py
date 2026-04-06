import unittest

from apps.workers.email_dispatch.worker import EmailDispatchWorker
from apps.workers.push_dispatch.worker import PushDispatchWorker


class StubPushDispatchWorker(PushDispatchWorker):
    def __init__(self) -> None:
        super().__init__()
        self.processed = []
        self.claimed = []

    async def process_outbox_message(self, outbox_id: str):
        self.processed.append(outbox_id)
        return {"processed": True, "delivered": True, "invalidated": 0}

    async def _claim_pending_ids(self):
        return list(self.claimed)


class StubEmailDispatchWorker(EmailDispatchWorker):
    def __init__(self) -> None:
        super().__init__()
        self.processed = []
        self.claimed = []

    async def process_outbox_message(self, outbox_id: str):
        self.processed.append(outbox_id)
        return {"processed": True, "delivered": True}

    async def _claim_pending_ids(self):
        return list(self.claimed)


class DispatchWorkersTest(unittest.IsolatedAsyncioTestCase):
    async def test_push_dispatch_process_event_routes_push_messages_only(self) -> None:
        worker = StubPushDispatchWorker()

        skipped = await worker.process_event(
            "notification.requested", {"outbox_id": "1", "channel": "email"}
        )
        processed = await worker.process_event(
            "notification.requested", {"outbox_id": "2", "channel": "push"}
        )

        self.assertFalse(skipped["processed"])
        self.assertTrue(processed["processed"])
        self.assertEqual(worker.processed, ["2"])

    async def test_email_dispatch_process_event_routes_email_messages_only(self) -> None:
        worker = StubEmailDispatchWorker()

        skipped = await worker.process_event(
            "notification.requested", {"outbox_id": "1", "channel": "push"}
        )
        processed = await worker.process_event(
            "notification.requested", {"outbox_id": "2", "channel": "email"}
        )

        self.assertFalse(skipped["processed"])
        self.assertTrue(processed["processed"])
        self.assertEqual(worker.processed, ["2"])

    async def test_push_dispatch_run_once_processes_claimed_outbox_ids(self) -> None:
        worker = StubPushDispatchWorker()
        worker.claimed = ["outbox-1", "outbox-2"]

        result = await worker.run_once()

        self.assertEqual(worker.processed, ["outbox-1", "outbox-2"])
        self.assertEqual(result, {"processed": 2, "delivered": 2, "failed": 0, "invalidated": 0})

    async def test_email_dispatch_run_once_processes_claimed_outbox_ids(self) -> None:
        worker = StubEmailDispatchWorker()
        worker.claimed = ["outbox-3"]

        result = await worker.run_once()

        self.assertEqual(worker.processed, ["outbox-3"])
        self.assertEqual(result, {"processed": 1, "delivered": 1, "failed": 0})


if __name__ == "__main__":
    unittest.main()
