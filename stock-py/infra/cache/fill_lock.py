from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Awaitable, Callable, Literal, TypeVar
from uuid import uuid4

from infra.cache.redis_client import get_redis
from infra.core.config import get_settings
from infra.observability.metrics import get_metrics_registry

logger = logging.getLogger(__name__)
metrics = get_metrics_registry()

T = TypeVar("T")

_RELEASE_FILL_LOCK_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""

_REFRESH_FILL_LOCK_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('EXPIRE', KEYS[1], ARGV[2])
end
return 0
"""


@dataclass(slots=True)
class CacheFillLockAttempt:
    status: Literal["acquired", "contended", "bypass"]
    token: str | None = None


def _cache_fill_lock_key(cache_key: str) -> str:
    return f"{cache_key}:fill-lock"


def _cache_fill_lock_refresh_interval_seconds(ttl_seconds: int) -> float:
    settings = get_settings()
    configured_ms = max(
        int(
            getattr(
                settings,
                "cache_fill_lock_refresh_interval_ms",
                max(ttl_seconds * 1000 // 3, 1),
            )
        ),
        1,
    )
    safe_max_ms = max(int(ttl_seconds * 1000 * 0.5), 1)
    return min(configured_ms, safe_max_ms) / 1000


async def try_acquire_cache_fill_lock(
    cache_key: str,
    metric_prefix: str,
) -> CacheFillLockAttempt:
    ttl_seconds = get_settings().cache_fill_lock_ttl_seconds
    if ttl_seconds <= 0:
        return CacheFillLockAttempt(status="bypass")

    token = uuid4().hex
    try:
        client = await get_redis()
        acquired = await client.set(
            _cache_fill_lock_key(cache_key),
            token,
            ex=ttl_seconds,
            nx=True,
        )
    except Exception:
        logger.warning("Cache fill lock acquisition failed for %s", cache_key, exc_info=True)
        metrics.counter(
            f"{metric_prefix}_distributed_lock_failures_total",
            "Failed distributed cache fill lock acquisitions",
        ).inc()
        return CacheFillLockAttempt(status="bypass")

    if acquired:
        metrics.counter(
            f"{metric_prefix}_distributed_lock_acquired_total",
            "Distributed cache fill locks acquired",
        ).inc()
        return CacheFillLockAttempt(status="acquired", token=token)

    metrics.counter(
        f"{metric_prefix}_distributed_lock_contention_total",
        "Distributed cache fill lock contentions",
    ).inc()
    return CacheFillLockAttempt(status="contended")


async def wait_for_distributed_cache_fill(
    cache_key: str,
    metric_prefix: str,
    cache_reader: Callable[[], Awaitable[T | None]],
) -> tuple[bool, T | None]:
    settings = get_settings()
    wait_timeout_ms = settings.cache_fill_lock_wait_timeout_ms
    if wait_timeout_ms <= 0:
        return False, None

    poll_interval_ms = max(int(settings.cache_fill_lock_poll_interval_ms), 1)
    deadline = perf_counter() + (wait_timeout_ms / 1000)
    lock_key = _cache_fill_lock_key(cache_key)

    try:
        client = await get_redis()
    except Exception:
        logger.warning("Cache fill lock wait setup failed for %s", cache_key, exc_info=True)
        metrics.counter(
            f"{metric_prefix}_distributed_wait_failures_total",
            "Failed distributed cache fill waits",
        ).inc()
        return False, None

    while perf_counter() < deadline:
        cached = await cache_reader()
        if cached is not None:
            metrics.counter(
                f"{metric_prefix}_distributed_wait_hits_total",
                "Distributed cache fill waits resolved from a remote fill",
            ).inc()
            return True, cached

        try:
            if not await client.exists(lock_key):
                metrics.counter(
                    f"{metric_prefix}_distributed_wait_aborted_total",
                    "Distributed cache fill waits that ended without a cached payload",
                ).inc()
                return False, None
        except Exception:
            logger.warning("Cache fill lock wait failed for %s", cache_key, exc_info=True)
            metrics.counter(
                f"{metric_prefix}_distributed_wait_failures_total",
                "Failed distributed cache fill waits",
            ).inc()
            return False, None

        await asyncio.sleep(poll_interval_ms / 1000)

    cached = await cache_reader()
    if cached is not None:
        metrics.counter(
            f"{metric_prefix}_distributed_wait_hits_total",
            "Distributed cache fill waits resolved from a remote fill",
        ).inc()
        return True, cached

    metrics.counter(
        f"{metric_prefix}_distributed_wait_timeouts_total",
        "Distributed cache fill waits that timed out",
    ).inc()
    return False, None


async def _renew_cache_fill_lock(
    cache_key: str,
    token: str,
    metric_prefix: str,
    ttl_seconds: int,
    refresh_interval_seconds: float,
) -> None:
    client = await get_redis()
    lock_key = _cache_fill_lock_key(cache_key)

    while True:
        await asyncio.sleep(refresh_interval_seconds)
        try:
            renewed = await client.eval(
                _REFRESH_FILL_LOCK_SCRIPT,
                1,
                lock_key,
                token,
                ttl_seconds,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Cache fill lock renewal failed for %s", cache_key, exc_info=True)
            metrics.counter(
                f"{metric_prefix}_distributed_renew_failures_total",
                "Failed distributed cache fill lock renewals",
            ).inc()
            continue

        if renewed:
            metrics.counter(
                f"{metric_prefix}_distributed_renewals_total",
                "Distributed cache fill lock renewals",
            ).inc()
            continue

        metrics.counter(
            f"{metric_prefix}_distributed_lock_lost_total",
            "Distributed cache fill locks lost before release",
        ).inc()
        return


def start_cache_fill_lock_renewal(
    cache_key: str,
    token: str | None,
    metric_prefix: str,
) -> asyncio.Task[None] | None:
    ttl_seconds = get_settings().cache_fill_lock_ttl_seconds
    if not token or ttl_seconds <= 0:
        return None

    refresh_interval_seconds = _cache_fill_lock_refresh_interval_seconds(ttl_seconds)
    if refresh_interval_seconds <= 0:
        return None

    return asyncio.create_task(
        _renew_cache_fill_lock(
            cache_key,
            token,
            metric_prefix,
            ttl_seconds,
            refresh_interval_seconds,
        )
    )


async def stop_cache_fill_lock_renewal(
    renewal_task: asyncio.Task[None] | None,
) -> None:
    if renewal_task is None:
        return

    renewal_task.cancel()
    try:
        await renewal_task
    except asyncio.CancelledError:
        return


async def release_cache_fill_lock(
    cache_key: str,
    token: str | None,
    metric_prefix: str,
) -> None:
    if not token:
        return

    try:
        client = await get_redis()
        await client.eval(
            _RELEASE_FILL_LOCK_SCRIPT,
            1,
            _cache_fill_lock_key(cache_key),
            token,
        )
    except Exception:
        logger.warning("Cache fill lock release failed for %s", cache_key, exc_info=True)
        metrics.counter(
            f"{metric_prefix}_distributed_release_failures_total",
            "Failed distributed cache fill lock releases",
        ).inc()
