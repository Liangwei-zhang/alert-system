from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any, TypeAlias

from sqlalchemy.ext.asyncio import AsyncSession

from infra.cache.fill_lock import (
    release_cache_fill_lock,
    start_cache_fill_lock_renewal,
    stop_cache_fill_lock_renewal,
    try_acquire_cache_fill_lock,
    wait_for_distributed_cache_fill,
)
from infra.cache.redis_client import get_redis
from infra.core.config import get_settings
from infra.observability.metrics import get_metrics_registry

logger = logging.getLogger(__name__)
metrics = get_metrics_registry()

_PENDING_ACCOUNT_PROFILE_CACHE_OPS_KEY = "pending_account_profile_cache_operations"
_ACCOUNT_PROFILE_CACHE_KEY_PREFIX = "account:profile:v1"
_account_profile_fill_futures: dict[int, asyncio.Future[dict[str, Any]]] = {}
_account_profile_fill_futures_lock = asyncio.Lock()


@dataclass(slots=True)
class AccountProfileCacheDelete:
    user_ids: tuple[int, ...]


AccountProfileCacheOperation: TypeAlias = AccountProfileCacheDelete


def _account_profile_cache_key(user_id: int) -> str:
    return f"{_ACCOUNT_PROFILE_CACHE_KEY_PREFIX}:{int(user_id)}"


def _consume_future_exception(future: asyncio.Future[dict[str, Any]]) -> None:
    try:
        future.exception()
    except asyncio.CancelledError:
        return


async def _claim_account_profile_fill(
    user_id: int,
) -> tuple[asyncio.Future[dict[str, Any]], bool]:
    async with _account_profile_fill_futures_lock:
        future = _account_profile_fill_futures.get(user_id)
        if future is not None:
            return future, False

        future = asyncio.get_running_loop().create_future()
        future.add_done_callback(_consume_future_exception)
        _account_profile_fill_futures[user_id] = future
        metrics.gauge(
            "account_profile_cache_fill_inflight",
            "In-flight account profile cache fills",
        ).inc()
        return future, True


async def _release_account_profile_fill(
    user_id: int,
    future: asyncio.Future[dict[str, Any]],
) -> None:
    async with _account_profile_fill_futures_lock:
        if _account_profile_fill_futures.get(user_id) is future:
            _account_profile_fill_futures.pop(user_id, None)
            metrics.gauge(
                "account_profile_cache_fill_inflight",
                "In-flight account profile cache fills",
            ).dec()


async def get_cached_account_profile(user_id: int) -> dict[str, Any] | None:
    try:
        client = await get_redis()
        raw_value = await client.get(_account_profile_cache_key(user_id))
    except Exception:
        logger.warning("Account profile cache read failed", exc_info=True)
        metrics.counter(
            "account_profile_cache_read_failures_total",
            "Failed account profile cache reads",
        ).inc()
        return None

    if raw_value in (None, ""):
        return None

    try:
        parsed = json.loads(raw_value)
    except (TypeError, ValueError, json.JSONDecodeError):
        logger.warning("Account profile cache contained invalid JSON")
        metrics.counter(
            "account_profile_cache_invalid_payload_total",
            "Invalid account profile cache payloads",
        ).inc()
        return None

    if isinstance(parsed, dict):
        return parsed

    logger.warning("Account profile cache contained a non-object payload")
    return None


async def cache_account_profile(
    user_id: int,
    payload: dict[str, Any],
    ttl_seconds: int | None = None,
) -> None:
    if ttl_seconds is None:
        ttl_seconds = get_settings().account_profile_cache_ttl_seconds
    if ttl_seconds <= 0:
        return

    try:
        client = await get_redis()
        await client.set(
            _account_profile_cache_key(user_id),
            json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
            ex=ttl_seconds,
        )
    except Exception:
        logger.warning("Account profile cache write failed", exc_info=True)
        metrics.counter(
            "account_profile_cache_write_failures_total",
            "Failed account profile cache writes",
        ).inc()


async def invalidate_account_profiles(user_ids: list[int] | tuple[int, ...]) -> None:
    keys = [_account_profile_cache_key(user_id) for user_id in user_ids if user_id is not None]
    if not keys:
        return

    try:
        client = await get_redis()
        await client.delete(*keys)
        metrics.counter(
            "account_profile_cache_invalidations_total",
            "Invalidated account profile cache entries",
        ).inc(len(keys))
    except Exception:
        logger.warning("Account profile cache delete failed", exc_info=True)
        metrics.counter(
            "account_profile_cache_invalidation_failures_total",
            "Failed account profile cache invalidations",
        ).inc()


async def get_or_load_account_profile(
    user_id: int,
    loader: Callable[[], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    cache_key = _account_profile_cache_key(user_id)
    cached = await get_cached_account_profile(user_id)
    if cached is not None:
        metrics.counter(
            "account_profile_cache_hits_total",
            "Account profile cache hits",
        ).inc()
        return cached

    metrics.counter(
        "account_profile_cache_misses_total",
        "Account profile cache misses",
    ).inc()
    future, is_owner = await _claim_account_profile_fill(user_id)
    if not is_owner:
        metrics.counter(
            "account_profile_cache_coalesced_total",
            "Account profile requests coalesced behind an in-flight fill",
        ).inc()
        return await future

    started_at = perf_counter()
    distributed_lock_token: str | None = None
    renewal_task: asyncio.Task[None] | None = None
    try:
        lock_attempt = await try_acquire_cache_fill_lock(cache_key, "account_profile_cache")
        if lock_attempt.status == "acquired":
            distributed_lock_token = lock_attempt.token
            renewal_task = start_cache_fill_lock_renewal(
                cache_key,
                distributed_lock_token,
                "account_profile_cache",
            )
        else:
            if lock_attempt.status == "contended":
                metrics.counter(
                    "account_profile_cache_distributed_coalesced_total",
                    "Account profile requests coalesced behind a remote in-flight fill",
                ).inc()
                resolved, remote_payload = await wait_for_distributed_cache_fill(
                    cache_key,
                    "account_profile_cache",
                    lambda: get_cached_account_profile(user_id),
                )
                if resolved:
                    if not future.done():
                        future.set_result(remote_payload)
                    return remote_payload

            metrics.counter(
                "account_profile_cache_distributed_bypass_total",
                "Account profile fills that bypassed distributed coalescing",
            ).inc()

        payload = await loader()
        await cache_account_profile(user_id, payload)
        if not future.done():
            future.set_result(payload)
        metrics.counter(
            "account_profile_cache_fills_total",
            "Account profile cache fills from the repository",
        ).inc()
        return payload
    except Exception as exc:
        if not future.done():
            future.set_exception(exc)
        metrics.counter(
            "account_profile_cache_fill_failures_total",
            "Failed account profile cache fills",
        ).inc()
        raise
    finally:
        metrics.histogram(
            "account_profile_cache_fill_duration_ms",
            "Account profile cache fill latency in milliseconds",
        ).observe((perf_counter() - started_at) * 1000)
        await stop_cache_fill_lock_renewal(renewal_task)
        await release_cache_fill_lock(
            cache_key,
            distributed_lock_token,
            "account_profile_cache",
        )
        await _release_account_profile_fill(user_id, future)


def schedule_invalidate_account_profile(
    session: AsyncSession | None,
    user_ids: int | list[int] | tuple[int, ...],
) -> None:
    if session is None:
        return

    if isinstance(user_ids, int):
        normalized = (int(user_ids),)
    else:
        normalized = tuple(int(user_id) for user_id in user_ids if user_id is not None)
    if not normalized:
        return

    operations = session.info.setdefault(_PENDING_ACCOUNT_PROFILE_CACHE_OPS_KEY, [])
    operations.append(AccountProfileCacheDelete(user_ids=normalized))


def pop_pending_account_profile_cache_operations(
    session: AsyncSession,
) -> list[AccountProfileCacheOperation]:
    operations = session.info.pop(_PENDING_ACCOUNT_PROFILE_CACHE_OPS_KEY, [])
    return list(operations)


async def apply_account_profile_cache_operations(
    operations: list[AccountProfileCacheOperation],
) -> None:
    user_ids = sorted({user_id for operation in operations for user_id in operation.user_ids})
    if user_ids:
        await invalidate_account_profiles(tuple(user_ids))
