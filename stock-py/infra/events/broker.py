from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from redis.exceptions import ResponseError

from infra.cache.redis_client import get_redis
from infra.core.config import get_settings
from infra.events.outbox import OutboxEvent, normalize_event


@dataclass(slots=True)
class BrokerMessage:
    message_id: str
    event: OutboxEvent


class EventBroker(Protocol):
    async def publish(self, event: OutboxEvent) -> str: ...

    async def publish_batch(self, events: list[OutboxEvent]) -> list[str]: ...

    async def consume_batch(
        self,
        *,
        consumer_name: str,
        count: int,
        block_ms: int,
    ) -> list[BrokerMessage]: ...

    async def acknowledge(self, message_id: str) -> int: ...


class RedisStreamEventBroker:
    def __init__(
        self,
        *,
        stream_name: str | None = None,
        group_name: str | None = None,
    ) -> None:
        settings = get_settings()
        self.stream_name = stream_name or settings.event_broker_stream_name
        self.group_name = group_name or settings.event_broker_group_name
        self.claim_idle_ms = settings.event_broker_claim_idle_ms
        self._group_initialized = False

    async def publish(self, event: OutboxEvent) -> str:
        client = await get_redis()
        return await client.xadd(self.stream_name, self._serialize_event(event))

    async def publish_batch(self, events: list[OutboxEvent]) -> list[str]:
        message_ids: list[str] = []
        for event in events:
            message_ids.append(await self.publish(event))
        return message_ids

    async def consume_batch(
        self,
        *,
        consumer_name: str,
        count: int,
        block_ms: int,
    ) -> list[BrokerMessage]:
        await self.ensure_consumer_group()
        client = await get_redis()
        reclaimed = await self._claim_stale_messages(
            client,
            consumer_name=consumer_name,
            count=count,
        )
        if reclaimed:
            return reclaimed
        response = await client.xreadgroup(
            self.group_name,
            consumer_name,
            {self.stream_name: ">"},
            count=count,
            block=block_ms,
        )
        return self._decode_stream_response(response)

    async def _claim_stale_messages(
        self,
        client,
        *,
        consumer_name: str,
        count: int,
    ) -> list[BrokerMessage]:
        entries: list[tuple[str, dict[str, str]]] = []
        next_start_id = "0-0"
        while len(entries) < count:
            next_start_id, claimed_entries, *_ = await client.xautoclaim(
                self.stream_name,
                self.group_name,
                consumer_name,
                self.claim_idle_ms,
                start_id=next_start_id,
                count=count - len(entries),
            )
            if not claimed_entries:
                break
            entries.extend(claimed_entries)
            if next_start_id == "0-0":
                break
        return self._decode_entries(entries)

    def _decode_stream_response(
        self, response: list[tuple[str, list[tuple[str, dict[str, str]]]]]
    ) -> list[BrokerMessage]:
        messages: list[BrokerMessage] = []
        for _stream, entries in response:
            messages.extend(self._decode_entries(entries))
        return messages

    def _decode_entries(self, entries: list[tuple[str, dict[str, str]]]) -> list[BrokerMessage]:
        messages: list[BrokerMessage] = []
        for message_id, fields in entries:
            messages.append(
                BrokerMessage(
                    message_id=message_id,
                    event=self._deserialize_event(fields),
                )
            )
        return messages

    async def acknowledge(self, message_id: str) -> int:
        client = await get_redis()
        return int(await client.xack(self.stream_name, self.group_name, message_id))

    async def ensure_consumer_group(self) -> None:
        if self._group_initialized:
            return
        client = await get_redis()
        try:
            await client.xgroup_create(
                self.stream_name,
                self.group_name,
                id="0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise
        self._group_initialized = True

    @staticmethod
    def _serialize_event(event: OutboxEvent) -> dict[str, str]:
        return {
            "topic": event.topic,
            "payload": json.dumps(event.payload, separators=(",", ":"), sort_keys=True),
            "key": event.key or "",
            "headers": json.dumps(event.headers, separators=(",", ":"), sort_keys=True),
            "occurred_at": event.occurred_at.isoformat(),
        }

    @staticmethod
    def _deserialize_event(fields: dict[str, str]) -> OutboxEvent:
        payload = json.loads(fields.get("payload", "{}"))
        headers = json.loads(fields.get("headers", "{}"))
        key = fields.get("key") or None
        occurred_at_raw = fields.get("occurred_at")
        occurred_at = None
        if occurred_at_raw:
            from datetime import datetime

            occurred_at = datetime.fromisoformat(occurred_at_raw.replace("Z", "+00:00"))
        return normalize_event(
            fields["topic"],
            payload,
            key=key,
            headers=headers,
            occurred_at=occurred_at,
        )


class KafkaEventBroker:
    def __init__(
        self,
        *,
        bootstrap_servers: str | None = None,
        topic_name: str | None = None,
        group_name: str | None = None,
        auto_offset_reset: str | None = None,
        producer_factory=None,
        consumer_factory=None,
        topic_partition_factory=None,
        offset_and_metadata_factory=None,
    ) -> None:
        settings = get_settings()
        self.bootstrap_servers = str(
            bootstrap_servers
            if bootstrap_servers is not None
            else settings.event_broker_kafka_bootstrap_servers
        ).strip()
        self.topic_name = str(
            topic_name if topic_name is not None else settings.event_broker_kafka_topic
        ).strip()
        self.group_name = str(
            group_name if group_name is not None else settings.event_broker_group_name
        ).strip()
        self.auto_offset_reset = str(
            auto_offset_reset
            if auto_offset_reset is not None
            else settings.event_broker_kafka_auto_offset_reset
        ).strip()
        self._producer_factory = producer_factory
        self._consumer_factory = consumer_factory
        self._topic_partition_factory = topic_partition_factory
        self._offset_and_metadata_factory = offset_and_metadata_factory
        self._producer = None
        self._consumers: dict[str, Any] = {}
        self._pending_acks: dict[str, str] = {}

    async def publish(self, event: OutboxEvent) -> str:
        producer = await self._get_producer()
        serialized = self._serialize_event(event)
        key = serialized["key"].encode("utf-8") if serialized["key"] else None
        if hasattr(producer, "send_and_wait"):
            metadata = await self._maybe_await(
                producer.send_and_wait(self.topic_name, key=key, value=serialized)
            )
        else:
            def _send() -> Any:
                future = producer.send(self.topic_name, key=key, value=serialized)
                return future.get(timeout=10)

            metadata = await self._to_thread(_send)
        return self._message_id(
            topic=str(getattr(metadata, "topic", self.topic_name)),
            partition=int(getattr(metadata, "partition", 0)),
            offset=int(getattr(metadata, "offset", 0)),
        )

    async def publish_batch(self, events: list[OutboxEvent]) -> list[str]:
        message_ids = [await self.publish(event) for event in events]
        producer = self._producer
        if producer is not None and hasattr(producer, "flush"):
            await self._maybe_await(producer.flush())
        return message_ids

    async def consume_batch(
        self,
        *,
        consumer_name: str,
        count: int,
        block_ms: int,
    ) -> list[BrokerMessage]:
        consumer = await self._get_consumer(consumer_name)
        if hasattr(consumer, "getmany"):
            response = await self._maybe_await(
                consumer.getmany(timeout_ms=max(int(block_ms), 1), max_records=count)
            )
        else:
            def _poll() -> dict[Any, list[Any]]:
                return consumer.poll(timeout_ms=max(int(block_ms), 1), max_records=count)

            response = await self._to_thread(_poll)
        messages: list[BrokerMessage] = []
        for topic_partition, records in response.items():
            for record in records:
                message_id = self._message_id(
                    topic=str(
                        getattr(record, "topic", getattr(topic_partition, "topic", self.topic_name))
                    ),
                    partition=int(
                        getattr(record, "partition", getattr(topic_partition, "partition", 0))
                    ),
                    offset=int(getattr(record, "offset", 0)),
                )
                self._pending_acks[message_id] = consumer_name
                messages.append(
                    BrokerMessage(
                        message_id=message_id,
                        event=self._deserialize_event(getattr(record, "value", {})),
                    )
                )
        return messages

    async def acknowledge(self, message_id: str) -> int:
        consumer_name = self._pending_acks.pop(message_id, None)
        if consumer_name is None:
            return 0
        consumer = self._consumers.get(consumer_name)
        if consumer is None:
            return 0

        topic, partition, offset = self._parse_message_id(message_id)
        topic_partition = self._build_topic_partition(topic, partition)
        offset_and_metadata = self._build_offset_and_metadata(offset + 1)
        if hasattr(consumer, "getmany"):
            await self._maybe_await(
                consumer.commit(offsets={topic_partition: offset_and_metadata})
            )
        else:
            def _commit() -> None:
                consumer.commit(offsets={topic_partition: offset_and_metadata})

            await self._to_thread(_commit)
        return 1

    async def _get_producer(self):
        if self._producer is None:
            producer = self._build_producer()
            if hasattr(producer, "start"):
                await self._maybe_await(producer.start())
            self._producer = producer
        return self._producer

    def _build_producer(self):
        if self._producer_factory is not None:
            return self._producer_factory()
        try:
            from aiokafka import AIOKafkaProducer
        except ImportError as exc:
            raise RuntimeError("Kafka event broker backend requires aiokafka") from exc
        return AIOKafkaProducer(
            bootstrap_servers=self._bootstrap_server_list(),
            value_serializer=lambda value: json.dumps(value, separators=(",", ":")).encode("utf-8"),
            linger_ms=5,
        )

    async def _get_consumer(self, consumer_name: str):
        consumer = self._consumers.get(consumer_name)
        if consumer is None:
            consumer = self._build_consumer(consumer_name)
            if hasattr(consumer, "start"):
                await self._maybe_await(consumer.start())
            self._consumers[consumer_name] = consumer
        return consumer

    def _build_consumer(self, consumer_name: str):
        if self._consumer_factory is not None:
            return self._consumer_factory(consumer_name)
        try:
            from aiokafka import AIOKafkaConsumer
        except ImportError as exc:
            raise RuntimeError("Kafka event broker backend requires aiokafka") from exc
        return AIOKafkaConsumer(
            self.topic_name,
            bootstrap_servers=self._bootstrap_server_list(),
            group_id=self.group_name,
            client_id=consumer_name,
            enable_auto_commit=False,
            auto_offset_reset=self.auto_offset_reset,
        )

    def _build_topic_partition(self, topic: str, partition: int):
        if self._topic_partition_factory is not None:
            return self._topic_partition_factory(topic, partition)
        try:
            from aiokafka.structs import TopicPartition
        except ImportError as exc:
            raise RuntimeError("Kafka event broker backend requires aiokafka") from exc
        return TopicPartition(topic, partition)

    def _build_offset_and_metadata(self, offset: int):
        if self._offset_and_metadata_factory is not None:
            return self._offset_and_metadata_factory(offset, None)
        return offset

    def _bootstrap_server_list(self) -> list[str]:
        return [item.strip() for item in self.bootstrap_servers.split(",") if item.strip()]

    @staticmethod
    async def _maybe_await(result: Any) -> Any:
        if inspect.isawaitable(result):
            return await result
        return result

    @staticmethod
    def _serialize_event(event: OutboxEvent) -> dict[str, str]:
        return {
            "topic": event.topic,
            "payload": json.dumps(event.payload, separators=(",", ":"), sort_keys=True),
            "key": event.key or "",
            "headers": json.dumps(event.headers, separators=(",", ":"), sort_keys=True),
            "occurred_at": event.occurred_at.isoformat(),
        }

    @staticmethod
    def _deserialize_event(value: Any) -> OutboxEvent:
        if isinstance(value, bytes):
            payload = json.loads(value.decode("utf-8"))
        elif isinstance(value, str):
            payload = json.loads(value)
        else:
            payload = dict(value or {})
        headers = json.loads(payload.get("headers", "{}"))
        body = json.loads(payload.get("payload", "{}"))
        key = payload.get("key") or None
        occurred_at_raw = payload.get("occurred_at")
        occurred_at = None
        if occurred_at_raw:
            from datetime import datetime

            occurred_at = datetime.fromisoformat(str(occurred_at_raw).replace("Z", "+00:00"))
        return normalize_event(
            payload["topic"],
            body,
            key=key,
            headers=headers,
            occurred_at=occurred_at,
        )

    @staticmethod
    def _message_id(*, topic: str, partition: int, offset: int) -> str:
        return f"{topic}:{partition}:{offset}"

    @staticmethod
    def _parse_message_id(message_id: str) -> tuple[str, int, int]:
        topic, partition, offset = message_id.rsplit(":", 2)
        return topic, int(partition), int(offset)

    @staticmethod
    async def _to_thread(function, /, *args, **kwargs):
        import asyncio

        return await asyncio.to_thread(function, *args, **kwargs)


@lru_cache(maxsize=1)
def get_event_broker() -> EventBroker:
    settings = get_settings()
    if settings.event_broker_backend == "kafka":
        return KafkaEventBroker()
    return RedisStreamEventBroker()
