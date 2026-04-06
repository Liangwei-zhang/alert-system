from __future__ import annotations

import asyncio
import logging
import os
import socket
from collections.abc import Callable
from typing import Any

from infra.core.config import get_settings
from infra.events.bootstrap import register_default_subscribers
from infra.events.broker import EventBroker, get_event_broker
from infra.events.bus import EventBus
from infra.events.outbox import EventOutboxRepository, event_from_record
from infra.observability.runtime_monitoring import run_runtime_monitored

logger = logging.getLogger(__name__)


class EventOutboxRelayWorker:
    def __init__(
        self,
        *,
        batch_size: int | None = None,
        broker: EventBroker | None = None,
        repository_factory: type[EventOutboxRepository] = EventOutboxRepository,
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        settings = get_settings()
        self.batch_size = batch_size or settings.event_broker_batch_size
        self.broker = broker or get_event_broker()
        self.repository_factory = repository_factory
        self.session_factory = session_factory
        self._running = False

    async def run_forever(self, poll_interval_seconds: float | None = None) -> None:
        self._running = True
        interval = poll_interval_seconds or get_settings().event_relay_poll_seconds
        while self._running:
            try:
                result = await self.run_once()
                if result["published"] == 0 and result["failed"] == 0:
                    await asyncio.sleep(interval)
            except Exception:
                logger.exception("Event outbox relay cycle failed")
                await asyncio.sleep(interval)

    async def run_once(self) -> dict[str, int]:
        session = await self.open_session()
        stats = {"claimed": 0, "published": 0, "failed": 0}
        try:
            repository = self.build_repository(session)
            records = await repository.claim_pending(limit=self.batch_size)
            stats["claimed"] = len(records)
            for record in records:
                try:
                    broker_message_id = await self.broker.publish(event_from_record(record))
                except Exception as exc:
                    await repository.requeue(record, error_message=str(exc))
                    stats["failed"] += 1
                    logger.exception(
                        "Failed publishing event_outbox id=%s topic=%s", record.id, record.topic
                    )
                    continue
                await repository.mark_published(record, broker_message_id=broker_message_id)
                stats["published"] += 1
            await self.commit_session(session)
            return stats
        finally:
            await self.close_session(session)

    def stop(self) -> None:
        self._running = False

    def build_repository(self, session: Any) -> EventOutboxRepository:
        return self.repository_factory(session)

    async def open_session(self) -> Any:
        if self.session_factory is None:
            from infra.db.session import get_session_factory

            self.session_factory = get_session_factory()
        return self.session_factory()

    async def commit_session(self, session: Any) -> None:
        commit = getattr(session, "commit", None)
        if callable(commit):
            result = commit()
            if hasattr(result, "__await__"):
                await result

    async def close_session(self, session: Any) -> None:
        close = getattr(session, "close", None)
        if callable(close):
            result = close()
            if hasattr(result, "__await__"):
                await result


class BrokerDispatchWorker:
    def __init__(
        self,
        *,
        broker: EventBroker | None = None,
        dispatch_bus: EventBus | None = None,
        batch_size: int | None = None,
        block_ms: int | None = None,
        consumer_name: str | None = None,
    ) -> None:
        settings = get_settings()
        self.broker = broker or get_event_broker()
        self.dispatch_bus = dispatch_bus or self._build_dispatch_bus()
        self.batch_size = batch_size or settings.event_broker_batch_size
        self.block_ms = block_ms or settings.event_broker_block_ms
        self.consumer_name = consumer_name or self._default_consumer_name()
        self._running = False

    async def run_forever(self) -> None:
        self._running = True
        while self._running:
            try:
                await self.run_once()
            except Exception:
                logger.exception("Broker dispatch cycle failed")
                await asyncio.sleep(1)

    async def run_once(self) -> dict[str, int]:
        messages = await self.broker.consume_batch(
            consumer_name=self.consumer_name,
            count=self.batch_size,
            block_ms=self.block_ms,
        )
        stats = {"consumed": len(messages), "acked": 0}
        for message in messages:
            await self.dispatch_bus.publish(message.event)
            await self.broker.acknowledge(message.message_id)
            stats["acked"] += 1
        return stats

    def stop(self) -> None:
        self._running = False

    @staticmethod
    def _build_dispatch_bus() -> EventBus:
        bus = EventBus()
        register_default_subscribers(bus)
        return bus

    @staticmethod
    def _default_consumer_name() -> str:
        return f"{socket.gethostname()}-{os.getpid()}"


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    relay = EventOutboxRelayWorker()
    dispatcher = BrokerDispatchWorker()

    async def runner() -> None:
        await asyncio.gather(relay.run_forever(), dispatcher.run_forever())

    await run_runtime_monitored(
        "event-pipeline",
        "worker",
        runner,
        metadata={"mode": "continuous"},
        heartbeat_interval_seconds=10,
        ttl_seconds=30,
        final_status="stopped",
    )


if __name__ == "__main__":
    asyncio.run(main())
