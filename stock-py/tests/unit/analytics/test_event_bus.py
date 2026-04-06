import unittest
from dataclasses import dataclass

from infra.events.bus import EventBus


@dataclass
class DummyEvent:
    topic: str
    payload: dict
    key: str | None = None


class EventBusTest(unittest.IsolatedAsyncioTestCase):
    async def test_publish_dispatches_to_all_subscribers_and_ignores_failures(self) -> None:
        bus = EventBus()
        calls = []

        async def successful_handler(topic, payload):
            calls.append((topic, payload["value"]))

        async def failing_handler(topic, payload):
            del topic, payload
            raise RuntimeError("boom")

        bus.subscribe("signal.generated", failing_handler, subscriber_id="failing")
        bus.subscribe("signal.generated", successful_handler, subscriber_id="successful")

        await bus.publish(DummyEvent(topic="signal.generated", payload={"value": 3}))

        self.assertEqual(calls, [("signal.generated", 3)])

    async def test_subscribe_deduplicates_same_subscriber_and_handler(self) -> None:
        bus = EventBus()
        calls = []

        async def handler(topic, payload):
            calls.append((topic, payload["value"]))

        bus.subscribe("notification.requested", handler, subscriber_id="worker")
        bus.subscribe("notification.requested", handler, subscriber_id="worker")

        await bus.publish(DummyEvent(topic="notification.requested", payload={"value": 7}))

        self.assertEqual(calls, [("notification.requested", 7)])


if __name__ == "__main__":
    unittest.main()
