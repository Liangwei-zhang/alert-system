import unittest
from datetime import UTC, datetime

from apps.workers.event_pipeline.worker import BrokerDispatchWorker, EventOutboxRelayWorker
from infra.events.bus import EventBus
from infra.events.outbox import OutboxEvent


class FakeBroker:
    def __init__(self) -> None:
        self.published = []
        self.messages = []
        self.acked = []

    async def publish(self, event: OutboxEvent) -> str:
        self.published.append(event)
        return f"msg-{len(self.published)}"

    async def consume_batch(self, *, consumer_name: str, count: int, block_ms: int):
        del consumer_name, count, block_ms
        return list(self.messages)

    async def acknowledge(self, message_id: str) -> int:
        self.acked.append(message_id)
        return 1


class FakeRecord:
    def __init__(self, record_id: str, topic: str, payload: dict) -> None:
        self.id = record_id
        self.topic = topic
        self.event_key = None
        self.payload = payload
        self.headers = {}
        self.occurred_at = datetime.now(UTC)


class FakeOutboxRepository:
    def __init__(self, records) -> None:
        self.records = list(records)
        self.published = []
        self.requeued = []

    async def claim_pending(self, limit: int = 100):
        del limit
        return list(self.records)

    async def mark_published(self, record, *, broker_message_id: str):
        self.published.append((record.id, broker_message_id))

    async def requeue(self, record, *, error_message: str):
        self.requeued.append((record.id, error_message))


class FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.closed = False

    async def commit(self) -> None:
        self.committed = True

    async def close(self) -> None:
        self.closed = True


class FakeBrokerMessage:
    def __init__(self, message_id: str, event: OutboxEvent) -> None:
        self.message_id = message_id
        self.event = event


class StubEventOutboxRelayWorker(EventOutboxRelayWorker):
    def __init__(self, *, repository: FakeOutboxRepository, broker: FakeBroker) -> None:
        super().__init__(broker=broker)
        self.repository = repository
        self.session = FakeSession()

    async def open_session(self):
        return self.session

    def build_repository(self, session):
        del session
        return self.repository


class EventPipelineWorkerTest(unittest.IsolatedAsyncioTestCase):
    async def test_outbox_relay_worker_publishes_claimed_events(self) -> None:
        repository = FakeOutboxRepository(
            [
                FakeRecord("evt-1", "signal.generated", {"symbol": "AAPL"}),
                FakeRecord("evt-2", "notification.requested", {"notification_id": "n-1"}),
            ]
        )
        broker = FakeBroker()
        worker = StubEventOutboxRelayWorker(repository=repository, broker=broker)

        result = await worker.run_once()

        self.assertEqual(result, {"claimed": 2, "published": 2, "failed": 0})
        self.assertEqual(
            [event.topic for event in broker.published],
            ["signal.generated", "notification.requested"],
        )
        self.assertEqual(repository.published, [("evt-1", "msg-1"), ("evt-2", "msg-2")])
        self.assertEqual(repository.requeued, [])
        self.assertTrue(worker.session.committed)
        self.assertTrue(worker.session.closed)

    async def test_broker_dispatch_worker_dispatches_and_acks_messages(self) -> None:
        broker = FakeBroker()
        calls = []
        bus = EventBus()

        async def handler(topic, payload):
            calls.append((topic, payload["value"]))

        bus.subscribe("signal.generated", handler, subscriber_id="handler")
        broker.messages = [
            FakeBrokerMessage(
                "1-0",
                OutboxEvent(topic="signal.generated", payload={"value": 7}),
            )
        ]
        worker = BrokerDispatchWorker(
            broker=broker,
            dispatch_bus=bus,
            consumer_name="test-consumer",
            batch_size=10,
            block_ms=1,
        )

        result = await worker.run_once()

        self.assertEqual(result, {"consumed": 1, "acked": 1})
        self.assertEqual(calls, [("signal.generated", 7)])
        self.assertEqual(broker.acked, ["1-0"])


if __name__ == "__main__":
    unittest.main()
