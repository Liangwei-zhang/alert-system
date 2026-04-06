from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import time
from uuid import uuid4

from infra.cache.redis_client import get_redis

DEFAULT_RETENTION_SECONDS = 7 * 24 * 60 * 60


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_key_part(value: str) -> str:
    return str(value or "unknown").strip().lower().replace(" ", "-")


def _metrics_hash_key(component: str, operation: str) -> str:
    normalized_component = _normalize_key_part(component)
    normalized_operation = _normalize_key_part(operation)
    return f"runtime_metrics:external:{normalized_component}:{normalized_operation}"


def _recent_key(component: str, operation: str, status: str) -> str:
    return f"{_metrics_hash_key(component, operation)}:recent:{_normalize_key_part(status)}"


@dataclass(slots=True)
class ExternalOperationSnapshot:
    component: str
    operation: str
    success_total: int = 0
    failure_total: int = 0
    success_recent: int = 0
    failure_recent: int = 0
    attempts_recent: int = 0
    failure_rate_percent: float = 0.0
    last_success_at: str | None = None
    last_failure_at: str | None = None
    last_error: str | None = None
    last_latency_ms: float | None = None


async def record_external_operation(
    component: str,
    operation: str,
    *,
    success: bool,
    error: str | None = None,
    latency_ms: float | None = None,
    retention_seconds: int = DEFAULT_RETENTION_SECONDS,
) -> None:
    try:
        client = await get_redis()
        metrics_key = _metrics_hash_key(component, operation)
        status_key = _recent_key(component, operation, "success" if success else "failure")
        now = utcnow()
        now_iso = now.isoformat().replace("+00:00", "Z")
        cutoff = now - timedelta(seconds=max(int(retention_seconds), 60))
        recent_member = f"{int(time() * 1000)}:{uuid4().hex}"
        await client.hincrby(metrics_key, "success_total" if success else "failure_total", 1)
        await client.hset(
            metrics_key, mapping={"last_latency_ms": str(round(float(latency_ms or 0.0), 2))}
        )
        if success:
            await client.hset(metrics_key, mapping={"last_success_at": now_iso})
        else:
            mapping = {"last_failure_at": now_iso}
            if error:
                mapping["last_error"] = error
            await client.hset(metrics_key, mapping=mapping)
        await client.zadd(status_key, {recent_member: now.timestamp()})
        await client.zremrangebyscore(status_key, 0, cutoff.timestamp())
        await client.expire(metrics_key, retention_seconds)
        await client.expire(status_key, retention_seconds)
    except Exception:
        return


async def get_external_operation_snapshot(
    component: str,
    operation: str,
    *,
    window_seconds: int,
) -> ExternalOperationSnapshot:
    metrics_key = _metrics_hash_key(component, operation)
    success_recent_key = _recent_key(component, operation, "success")
    failure_recent_key = _recent_key(component, operation, "failure")
    window = max(int(window_seconds), 60)
    snapshot = ExternalOperationSnapshot(component=component, operation=operation)

    try:
        client = await get_redis()
        now_score = utcnow().timestamp()
        min_score = now_score - window
        metrics = await client.hgetall(metrics_key)
        success_recent = int(await client.zcount(success_recent_key, min_score, now_score) or 0)
        failure_recent = int(await client.zcount(failure_recent_key, min_score, now_score) or 0)
        attempts_recent = success_recent + failure_recent
        failure_rate_percent = 0.0
        if attempts_recent > 0:
            failure_rate_percent = round((failure_recent / attempts_recent) * 100, 2)

        snapshot.success_total = int(metrics.get("success_total") or 0)
        snapshot.failure_total = int(metrics.get("failure_total") or 0)
        snapshot.success_recent = success_recent
        snapshot.failure_recent = failure_recent
        snapshot.attempts_recent = attempts_recent
        snapshot.failure_rate_percent = failure_rate_percent
        snapshot.last_success_at = metrics.get("last_success_at") or None
        snapshot.last_failure_at = metrics.get("last_failure_at") or None
        snapshot.last_error = metrics.get("last_error") or None
        last_latency_ms = metrics.get("last_latency_ms")
        snapshot.last_latency_ms = (
            float(last_latency_ms) if last_latency_ms not in (None, "") else None
        )
    except Exception:
        return snapshot

    return snapshot
