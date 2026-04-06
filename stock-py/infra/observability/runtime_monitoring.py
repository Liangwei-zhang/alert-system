from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from typing import Any

from infra.cache.redis_client import get_json, get_redis

logger = logging.getLogger(__name__)

RUNTIME_MONITOR_INDEX_KEY = "runtime_monitoring:index"
RUNTIME_MONITOR_KEY_PREFIX = "runtime_monitoring:component"

EXPECTED_RUNTIME_COMPONENTS: tuple[tuple[str, str], ...] = (
    ("scheduler", "scheduler"),
    ("worker", "event-pipeline"),
    ("worker", "retention"),
    ("worker", "tradingagents-bridge"),
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_runtime_component_key(component_kind: str, component_name: str) -> str:
    normalized_kind = str(component_kind).strip().lower()
    normalized_name = str(component_name).strip().lower()
    return f"{RUNTIME_MONITOR_KEY_PREFIX}:{normalized_kind}:{normalized_name}"


def get_expected_runtime_components() -> list[dict[str, Any]]:
    return [
        {
            "component_kind": component_kind,
            "component_name": component_name,
        }
        for component_kind, component_name in EXPECTED_RUNTIME_COMPONENTS
    ]


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def _calculate_health(snapshot: dict[str, Any], now: datetime) -> str:
    status = str(snapshot.get("status") or "unknown").lower()
    expires_at = snapshot.get("expires_at")
    if status == "failed":
        return "error"
    if status in {"completed", "stopped", "cancelled"}:
        return "inactive"
    if not expires_at:
        return "unknown"
    expires_at_value = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
    if expires_at_value < now:
        return "stale"
    return "healthy"


def _finalize_snapshot(snapshot: dict[str, Any], now: datetime) -> dict[str, Any]:
    last_heartbeat_at = snapshot.get("last_heartbeat_at")
    age_seconds: float | None = None
    if last_heartbeat_at:
        last_heartbeat_at_value = datetime.fromisoformat(
            str(last_heartbeat_at).replace("Z", "+00:00")
        )
        age_seconds = max((now - last_heartbeat_at_value).total_seconds(), 0.0)
    snapshot["age_seconds"] = age_seconds
    snapshot["health"] = _calculate_health(snapshot, now)
    snapshot["is_expected"] = bool(snapshot.get("is_expected", False))
    snapshot["metadata"] = dict(snapshot.get("metadata") or {})
    return snapshot


def _missing_snapshot(component_kind: str, component_name: str, now: datetime) -> dict[str, Any]:
    return {
        "component_kind": component_kind,
        "component_name": component_name,
        "status": "missing",
        "health": "missing",
        "last_heartbeat_at": None,
        "started_at": None,
        "expires_at": None,
        "ttl_seconds": None,
        "heartbeat_count": 0,
        "host": None,
        "pid": None,
        "metadata": {},
        "age_seconds": None,
        "is_expected": True,
        "recorded_at": now.isoformat().replace("+00:00", "Z"),
    }


async def record_runtime_snapshot(
    component_name: str,
    component_kind: str,
    status: str,
    *,
    metadata: dict[str, Any] | None = None,
    ttl_seconds: int | None = None,
) -> dict[str, Any]:
    now = utcnow()
    key = build_runtime_component_key(component_kind, component_name)
    client = await get_redis()
    existing = await get_json(key) or {}
    ttl = max(int(ttl_seconds or 30), 5)

    snapshot = {
        "component_kind": str(component_kind).strip().lower(),
        "component_name": str(component_name).strip().lower(),
        "status": str(status).strip().lower(),
        "started_at": existing.get("started_at") or now.isoformat().replace("+00:00", "Z"),
        "last_heartbeat_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(seconds=ttl)).isoformat().replace("+00:00", "Z"),
        "ttl_seconds": ttl,
        "heartbeat_count": int(existing.get("heartbeat_count") or 0) + 1,
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "metadata": dict(metadata or existing.get("metadata") or {}),
        "is_expected": (str(component_kind).strip().lower(), str(component_name).strip().lower())
        in EXPECTED_RUNTIME_COMPONENTS,
    }

    await client.sadd(RUNTIME_MONITOR_INDEX_KEY, key)
    await client.set(key, json.dumps(snapshot, default=_json_default), ex=ttl)
    return _finalize_snapshot(snapshot, now)


async def list_runtime_components(component_kind: str | None = None) -> list[dict[str, Any]]:
    normalized_kind = str(component_kind).strip().lower() if component_kind else None
    client = await get_redis()
    now = utcnow()
    raw_keys = await client.smembers(RUNTIME_MONITOR_INDEX_KEY)
    stale_keys: list[str] = []
    actual_components: dict[tuple[str, str], dict[str, Any]] = {}

    for raw_key in raw_keys:
        payload = await get_json(str(raw_key))
        if payload is None:
            stale_keys.append(str(raw_key))
            continue
        component_key = (
            str(payload.get("component_kind") or "unknown").lower(),
            str(payload.get("component_name") or "unknown").lower(),
        )
        actual_components[component_key] = _finalize_snapshot(dict(payload), now)

    if stale_keys:
        await client.srem(RUNTIME_MONITOR_INDEX_KEY, *stale_keys)

    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for component_kind_value, component_name_value in EXPECTED_RUNTIME_COMPONENTS:
        component_key = (component_kind_value, component_name_value)
        merged[component_key] = actual_components.get(
            component_key,
            _missing_snapshot(component_kind_value, component_name_value, now),
        )

    for component_key, snapshot in actual_components.items():
        merged.setdefault(component_key, snapshot)

    components = list(merged.values())
    if normalized_kind is not None:
        components = [
            component for component in components if component["component_kind"] == normalized_kind
        ]

    return sorted(
        components,
        key=lambda item: (item["component_kind"], item["component_name"]),
    )


async def get_runtime_component(
    component_kind: str,
    component_name: str,
) -> dict[str, Any] | None:
    normalized_kind = str(component_kind).strip().lower()
    normalized_name = str(component_name).strip().lower()
    components = await list_runtime_components(component_kind=normalized_kind)
    for component in components:
        if component["component_name"] == normalized_name:
            return component
    return None


async def run_runtime_monitored(
    component_name: str,
    component_kind: str,
    runner: Callable[[], Awaitable[Any]],
    *,
    metadata: dict[str, Any] | None = None,
    heartbeat_interval_seconds: float = 10.0,
    ttl_seconds: int | None = None,
    final_status: str = "completed",
) -> Any:
    interval = max(float(heartbeat_interval_seconds), 1.0)
    ttl = max(int(ttl_seconds or interval * 3), 5)
    stop_event = asyncio.Event()

    async def heartbeat_loop() -> None:
        while not stop_event.is_set():
            try:
                await record_runtime_snapshot(
                    component_name,
                    component_kind,
                    "running",
                    metadata=metadata,
                    ttl_seconds=ttl,
                )
            except Exception:
                logger.exception(
                    "Failed recording runtime heartbeat kind=%s name=%s",
                    component_kind,
                    component_name,
                )

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
            except TimeoutError:
                continue

    await record_runtime_snapshot(
        component_name,
        component_kind,
        "starting",
        metadata=metadata,
        ttl_seconds=ttl,
    )
    task = asyncio.create_task(heartbeat_loop())

    try:
        result = await runner()
    except asyncio.CancelledError:
        await record_runtime_snapshot(
            component_name,
            component_kind,
            "cancelled",
            metadata=dict(metadata or {}),
            ttl_seconds=ttl,
        )
        raise
    except Exception as exc:
        failure_metadata = dict(metadata or {})
        failure_metadata["error"] = f"{type(exc).__name__}: {exc}"
        await record_runtime_snapshot(
            component_name,
            component_kind,
            "failed",
            metadata=failure_metadata,
            ttl_seconds=ttl,
        )
        raise
    else:
        success_metadata = dict(metadata or {})
        if isinstance(result, dict):
            success_metadata["last_result"] = result
        elif result is not None:
            success_metadata["last_result"] = str(result)
        await record_runtime_snapshot(
            component_name,
            component_kind,
            final_status,
            metadata=success_metadata,
            ttl_seconds=ttl,
        )
        return result
    finally:
        stop_event.set()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
