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

_PENDING_TRADE_INFO_CACHE_OPS_KEY = "pending_trade_info_cache_operations"
_TRADE_INFO_CACHE_KEY_PREFIX = "trade:info:v1"
_trade_info_fill_futures: dict[str, asyncio.Future[dict[str, Any] | None]] = {}
_trade_info_fill_futures_lock = asyncio.Lock()


@dataclass(slots=True)
class TradeInfoCacheDelete:
    trade_ids: tuple[str, ...]


TradeInfoCacheOperation: TypeAlias = TradeInfoCacheDelete


def _trade_info_cache_key(trade_id: str) -> str:
    return f"{_TRADE_INFO_CACHE_KEY_PREFIX}:{trade_id}"


def _consume_future_exception(future: asyncio.Future[dict[str, Any] | None]) -> None:
    try:
        future.exception()
    except asyncio.CancelledError:
        return


async def _claim_trade_info_fill(
    trade_id: str,
) -> tuple[asyncio.Future[dict[str, Any] | None], bool]:
    async with _trade_info_fill_futures_lock:
        future = _trade_info_fill_futures.get(trade_id)
        if future is not None:
            return future, False

        future = asyncio.get_running_loop().create_future()
        future.add_done_callback(_consume_future_exception)
        _trade_info_fill_futures[trade_id] = future
        metrics.gauge(
            "trade_info_cache_fill_inflight",
            "In-flight trade info cache fills",
        ).inc()
        return future, True


async def _release_trade_info_fill(
    trade_id: str,
    future: asyncio.Future[dict[str, Any] | None],
) -> None:
    async with _trade_info_fill_futures_lock:
        if _trade_info_fill_futures.get(trade_id) is future:
            _trade_info_fill_futures.pop(trade_id, None)
            metrics.gauge(
                "trade_info_cache_fill_inflight",
                "In-flight trade info cache fills",
            ).dec()


async def get_cached_trade_snapshot(trade_id: str) -> dict[str, Any] | None:
    try:
        client = await get_redis()
        raw_value = await client.get(_trade_info_cache_key(trade_id))
    except Exception:
        logger.warning("Trade info cache read failed", exc_info=True)
        metrics.counter(
            "trade_info_cache_read_failures_total",
            "Failed trade info cache reads",
        ).inc()
        return None

    if raw_value in (None, ""):
        return None

    try:
        parsed = json.loads(raw_value)
    except (TypeError, ValueError, json.JSONDecodeError):
        logger.warning("Trade info cache contained invalid JSON")
        metrics.counter(
            "trade_info_cache_invalid_payload_total",
            "Invalid trade info cache payloads",
        ).inc()
        return None

    if isinstance(parsed, dict):
        return parsed

    logger.warning("Trade info cache contained a non-object payload")
    return None


async def cache_trade_snapshot(
    trade_id: str,
    payload: dict[str, Any],
    ttl_seconds: int | None = None,
) -> None:
    if ttl_seconds is None:
        ttl_seconds = get_settings().trade_info_cache_ttl_seconds
    if ttl_seconds <= 0:
        return

    try:
        client = await get_redis()
        await client.set(
            _trade_info_cache_key(trade_id),
            json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
            ex=ttl_seconds,
        )
    except Exception:
        logger.warning("Trade info cache write failed", exc_info=True)
        metrics.counter(
            "trade_info_cache_write_failures_total",
            "Failed trade info cache writes",
        ).inc()


async def invalidate_trade_snapshots(trade_ids: list[str] | tuple[str, ...]) -> None:
    keys = [_trade_info_cache_key(trade_id) for trade_id in trade_ids if trade_id]
    if not keys:
        return

    try:
        client = await get_redis()
        await client.delete(*keys)
        metrics.counter(
            "trade_info_cache_invalidations_total",
            "Invalidated trade info cache entries",
        ).inc(len(keys))
    except Exception:
        logger.warning("Trade info cache delete failed", exc_info=True)
        metrics.counter(
            "trade_info_cache_invalidation_failures_total",
            "Failed trade info cache invalidations",
        ).inc()


async def get_or_load_trade_snapshot(
    trade_id: str,
    loader: Callable[[], Awaitable[dict[str, Any] | None]],
) -> dict[str, Any] | None:
    cache_key = _trade_info_cache_key(trade_id)
    cached = await get_cached_trade_snapshot(trade_id)
    if cached is not None:
        metrics.counter(
            "trade_info_cache_hits_total",
            "Trade info cache hits",
        ).inc()
        return cached

    metrics.counter(
        "trade_info_cache_misses_total",
        "Trade info cache misses",
    ).inc()
    future, is_owner = await _claim_trade_info_fill(trade_id)
    if not is_owner:
        metrics.counter(
            "trade_info_cache_coalesced_total",
            "Trade info requests coalesced behind an in-flight fill",
        ).inc()
        return await future

    started_at = perf_counter()
    distributed_lock_token: str | None = None
    renewal_task: asyncio.Task[None] | None = None
    try:
        lock_attempt = await try_acquire_cache_fill_lock(cache_key, "trade_info_cache")
        if lock_attempt.status == "acquired":
            distributed_lock_token = lock_attempt.token
            renewal_task = start_cache_fill_lock_renewal(
                cache_key,
                distributed_lock_token,
                "trade_info_cache",
            )
        else:
            if lock_attempt.status == "contended":
                metrics.counter(
                    "trade_info_cache_distributed_coalesced_total",
                    "Trade info requests coalesced behind a remote in-flight fill",
                ).inc()
                resolved, remote_payload = await wait_for_distributed_cache_fill(
                    cache_key,
                    "trade_info_cache",
                    lambda: get_cached_trade_snapshot(trade_id),
                )
                if resolved:
                    if not future.done():
                        future.set_result(remote_payload)
                    return remote_payload

            metrics.counter(
                "trade_info_cache_distributed_bypass_total",
                "Trade info fills that bypassed distributed coalescing",
            ).inc()

        payload = await loader()
        if payload is not None:
            await cache_trade_snapshot(trade_id, payload)
            metrics.counter(
                "trade_info_cache_fills_total",
                "Trade info cache fills from the repository",
            ).inc()
        if not future.done():
            future.set_result(payload)
        return payload
    except Exception as exc:
        if not future.done():
            future.set_exception(exc)
        metrics.counter(
            "trade_info_cache_fill_failures_total",
            "Failed trade info cache fills",
        ).inc()
        raise
    finally:
        metrics.histogram(
            "trade_info_cache_fill_duration_ms",
            "Trade info cache fill latency in milliseconds",
        ).observe((perf_counter() - started_at) * 1000)
        await stop_cache_fill_lock_renewal(renewal_task)
        await release_cache_fill_lock(
            cache_key,
            distributed_lock_token,
            "trade_info_cache",
        )
        await _release_trade_info_fill(trade_id, future)


def schedule_invalidate_trade_info(
    session: AsyncSession | None,
    trade_ids: str | list[str] | tuple[str, ...],
) -> None:
    if session is None:
        return

    if isinstance(trade_ids, str):
        normalized = (trade_ids,)
    else:
        normalized = tuple(str(trade_id) for trade_id in trade_ids if trade_id)
    if not normalized:
        return

    operations = session.info.setdefault(_PENDING_TRADE_INFO_CACHE_OPS_KEY, [])
    operations.append(TradeInfoCacheDelete(trade_ids=normalized))


def pop_pending_trade_info_cache_operations(
    session: AsyncSession,
) -> list[TradeInfoCacheOperation]:
    operations = session.info.pop(_PENDING_TRADE_INFO_CACHE_OPS_KEY, [])
    return list(operations)


async def apply_trade_info_cache_operations(
    operations: list[TradeInfoCacheOperation],
) -> None:
    trade_ids = sorted({trade_id for operation in operations for trade_id in operation.trade_ids})
    if trade_ids:
        await invalidate_trade_snapshots(tuple(trade_ids))
