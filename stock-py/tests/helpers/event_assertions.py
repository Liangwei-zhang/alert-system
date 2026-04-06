from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def assert_outbox_event(
    events: Iterable[dict[str, Any]],
    *,
    topic: str,
    **expected_fields: Any,
) -> dict[str, Any]:
    for event in events:
        if event.get("topic") != topic:
            continue
        if all(event.get(key) == value for key, value in expected_fields.items()):
            return event
    expected = {"topic": topic, **expected_fields}
    raise AssertionError(f"Expected outbox event not found: {expected}")


def assert_kafka_event(
    events: Iterable[dict[str, Any]],
    *,
    topic: str,
    **expected_fields: Any,
) -> dict[str, Any]:
    return assert_outbox_event(events, topic=topic, **expected_fields)
