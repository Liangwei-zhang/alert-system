from __future__ import annotations

import logging
from collections import defaultdict
from functools import lru_cache
from inspect import isawaitable
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Sequence

if TYPE_CHECKING:
    from infra.events.outbox import OutboxEvent

logger = logging.getLogger(__name__)

EventHandler = Callable[[str, dict[str, Any]], Awaitable[Any] | Any]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[tuple[str, EventHandler]]] = defaultdict(list)

    async def publish(self, event: "OutboxEvent") -> None:
        logger.info("Published event topic=%s key=%s", event.topic, event.key)
        for subscriber_id, handler in list(self._subscribers.get(event.topic, [])):
            try:
                result = handler(event.topic, dict(event.payload))
                if isawaitable(result):
                    await result
            except Exception:
                logger.exception(
                    "Event subscriber failed topic=%s subscriber=%s",
                    event.topic,
                    subscriber_id,
                )

    async def publish_batch(self, events: Sequence["OutboxEvent"]) -> None:
        for event in events:
            await self.publish(event)

    def subscribe(
        self, topic: str, handler: EventHandler, *, subscriber_id: str | None = None
    ) -> None:
        normalized_subscriber_id = subscriber_id or self._infer_subscriber_id(handler)
        subscribers = self._subscribers[topic]
        for existing_id, existing_handler in subscribers:
            if existing_id == normalized_subscriber_id and existing_handler == handler:
                return
        subscribers.append((normalized_subscriber_id, handler))

    def clear_subscribers(self) -> None:
        self._subscribers.clear()

    def has_subscribers(self) -> bool:
        return any(self._subscribers.values())

    @staticmethod
    def _infer_subscriber_id(handler: EventHandler) -> str:
        owner = getattr(handler, "__self__", None)
        if owner is not None:
            return owner.__class__.__name__
        return getattr(handler, "__name__", handler.__class__.__name__)


@lru_cache(maxsize=1)
def get_event_bus() -> EventBus:
    bus = EventBus()
    from infra.events.bootstrap import register_default_subscribers

    register_default_subscribers(bus)
    return bus
