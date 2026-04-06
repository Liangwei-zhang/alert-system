import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from infra.events.broker import KafkaEventBroker, RedisStreamEventBroker, get_event_broker
from infra.events.outbox import normalize_event


class FakeRedisClient:
    def __init__(self, *, reclaimed=None, new_messages=None) -> None:
        self.reclaimed = reclaimed or []
        self.new_messages = new_messages or []
        self.group_creates = []
        self.autoclaim_calls = []
        self.readgroup_calls = []

    async def xgroup_create(self, stream_name, group_name, id="0", mkstream=True):
        self.group_creates.append((stream_name, group_name, id, mkstream))
        return True

    async def xautoclaim(
        self,
        stream_name,
        group_name,
        consumer_name,
        min_idle_time,
        *,
        start_id="0-0",
        count=None,
    ):
        self.autoclaim_calls.append(
            (stream_name, group_name, consumer_name, min_idle_time, start_id, count)
        )
        return ("0-0", list(self.reclaimed), [])

    async def xreadgroup(self, group_name, consumer_name, streams, *, count=None, block=None):
        self.readgroup_calls.append((group_name, consumer_name, streams, count, block))
        if not self.new_messages:
            return []
        stream_name = next(iter(streams.keys()))
        return [(stream_name, list(self.new_messages))]


class FakeKafkaFuture:
    def __init__(self, metadata) -> None:
        self.metadata = metadata

    def get(self, timeout=None):
        del timeout
        return self.metadata


class FakeKafkaProducer:
    def __init__(self) -> None:
        self.sent = []
        self.flushed = False

    def send(self, topic, *, key=None, value=None):
        self.sent.append({"topic": topic, "key": key, "value": value})
        metadata = SimpleNamespace(topic=topic, partition=0, offset=len(self.sent) - 1)
        return FakeKafkaFuture(metadata)

    def flush(self) -> None:
        self.flushed = True


class FakeKafkaConsumer:
    def __init__(self, records=None) -> None:
        self.records = records or {}
        self.commit_calls = []

    def poll(self, timeout_ms=None, max_records=None):
        del timeout_ms, max_records
        return dict(self.records)

    def commit(self, offsets=None):
        self.commit_calls.append(offsets or {})


class FakeTopicPartition:
    def __init__(self, topic: str, partition: int) -> None:
        self.topic = topic
        self.partition = partition

    def __hash__(self) -> int:
        return hash((self.topic, self.partition))

    def __eq__(self, other) -> bool:
        return isinstance(other, FakeTopicPartition) and (
            self.topic,
            self.partition,
        ) == (other.topic, other.partition)


class RedisStreamEventBrokerTest(unittest.IsolatedAsyncioTestCase):
    async def test_consume_batch_claims_stale_messages_before_new_messages(self) -> None:
        client = FakeRedisClient(
            reclaimed=[
                (
                    "1-0",
                    {
                        "topic": "signal.generated",
                        "payload": '{"symbol":"AAPL"}',
                        "headers": "{}",
                        "key": "",
                        "occurred_at": "2026-04-04T00:00:00+00:00",
                    },
                )
            ]
        )
        broker = RedisStreamEventBroker(stream_name="events", group_name="dispatchers")

        with patch("infra.events.broker.get_redis", AsyncMock(return_value=client)):
            messages = await broker.consume_batch(
                consumer_name="worker-1",
                count=10,
                block_ms=1,
            )

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].message_id, "1-0")
        self.assertEqual(messages[0].event.topic, "signal.generated")
        self.assertEqual(messages[0].event.payload, {"symbol": "AAPL"})
        self.assertEqual(client.readgroup_calls, [])

    async def test_consume_batch_reads_new_messages_when_no_stale_messages(self) -> None:
        client = FakeRedisClient(
            new_messages=[
                (
                    "2-0",
                    {
                        "topic": "notification.requested",
                        "payload": '{"notification_id":"n-1"}',
                        "headers": "{}",
                        "key": "",
                        "occurred_at": "2026-04-04T00:00:00+00:00",
                    },
                )
            ]
        )
        broker = RedisStreamEventBroker(stream_name="events", group_name="dispatchers")

        with patch("infra.events.broker.get_redis", AsyncMock(return_value=client)):
            messages = await broker.consume_batch(
                consumer_name="worker-2",
                count=10,
                block_ms=5,
            )

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].message_id, "2-0")
        self.assertEqual(messages[0].event.topic, "notification.requested")
        self.assertEqual(client.readgroup_calls[0][0], "dispatchers")


class KafkaEventBrokerTest(unittest.IsolatedAsyncioTestCase):
    async def test_publish_consume_and_acknowledge(self) -> None:
        producer = FakeKafkaProducer()
        topic_partition = FakeTopicPartition("stock-py.events", 0)
        consumer = FakeKafkaConsumer(
            records={
                topic_partition: [
                    SimpleNamespace(
                        topic="stock-py.events",
                        partition=0,
                        offset=4,
                        value={
                            "topic": "signal.generated",
                            "payload": '{"symbol":"AAPL"}',
                            "headers": "{}",
                            "key": "",
                            "occurred_at": "2026-04-04T00:00:00+00:00",
                        },
                    )
                ]
            }
        )
        broker = KafkaEventBroker(
            bootstrap_servers="kafka:9092",
            topic_name="stock-py.events",
            group_name="dispatchers",
            producer_factory=lambda: producer,
            consumer_factory=lambda consumer_name: consumer,
            topic_partition_factory=lambda topic, partition: FakeTopicPartition(topic, partition),
            offset_and_metadata_factory=lambda offset, metadata: {
                "offset": offset,
                "metadata": metadata,
            },
        )

        publish_id = await broker.publish(normalize_event("signal.generated", {"symbol": "MSFT"}))
        messages = await broker.consume_batch(consumer_name="worker-1", count=10, block_ms=1)
        acked = await broker.acknowledge(messages[0].message_id)

        self.assertEqual(publish_id, "stock-py.events:0:0")
        self.assertEqual(len(producer.sent), 1)
        self.assertEqual(messages[0].message_id, "stock-py.events:0:4")
        self.assertEqual(messages[0].event.payload, {"symbol": "AAPL"})
        self.assertEqual(acked, 1)
        self.assertEqual(
            consumer.commit_calls,
            [
                {
                    FakeTopicPartition("stock-py.events", 0): {
                        "offset": 5,
                        "metadata": None,
                    }
                }
            ],
        )


class EventBrokerFactoryTest(unittest.TestCase):
    def tearDown(self) -> None:
        get_event_broker.cache_clear()

    def test_get_event_broker_returns_kafka_backend_when_configured(self) -> None:
        with patch("infra.events.broker.get_settings") as mock_get_settings:
            mock_get_settings.return_value = SimpleNamespace(
                event_broker_backend="kafka",
                event_broker_kafka_bootstrap_servers="kafka:9092",
                event_broker_kafka_topic="stock-py.events",
                event_broker_group_name="dispatchers",
                event_broker_kafka_auto_offset_reset="earliest",
            )

            broker = get_event_broker()

        self.assertIsInstance(broker, KafkaEventBroker)

    def test_get_event_broker_returns_redis_backend_by_default(self) -> None:
        with patch("infra.events.broker.get_settings") as mock_get_settings:
            mock_get_settings.return_value = SimpleNamespace(
                event_broker_backend="redis",
                event_broker_stream_name="stock-py.events",
                event_broker_group_name="dispatchers",
                event_broker_claim_idle_ms=30000,
            )

            broker = get_event_broker()

        self.assertIsInstance(broker, RedisStreamEventBroker)


if __name__ == "__main__":
    unittest.main()
