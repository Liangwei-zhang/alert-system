from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TypeAlias

from sqlalchemy.ext.asyncio import AsyncSession

from infra.cache.redis_client import get_redis

logger = logging.getLogger(__name__)

_PENDING_SESSION_CACHE_OPS_KEY = "pending_session_cache_operations"
_SESSION_CACHE_KEY_PREFIX = "session:active"


@dataclass(slots=True)
class SessionCacheUpsert:
    token_hash: str
    user_id: int
    expires_at: datetime


@dataclass(slots=True)
class SessionCacheDelete:
    token_hashes: tuple[str, ...]


SessionCacheOperation: TypeAlias = SessionCacheUpsert | SessionCacheDelete


def _session_cache_key(token_hash: str) -> str:
    return f"{_SESSION_CACHE_KEY_PREFIX}:{token_hash}"


async def get_cached_session_user_id(token_hash: str) -> int | None:
    try:
        client = await get_redis()
        raw_value = await client.get(_session_cache_key(token_hash))
    except Exception:
        logger.warning("Session cache read failed", exc_info=True)
        return None

    if raw_value in (None, ""):
        return None

    try:
        return int(raw_value)
    except (TypeError, ValueError):
        logger.warning("Session cache contained a non-integer user id")
        return None


async def cache_active_session(token_hash: str, user_id: int, expires_at: datetime) -> None:
    ttl_seconds = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    if ttl_seconds <= 0:
        return

    try:
        client = await get_redis()
        await client.set(_session_cache_key(token_hash), str(user_id), ex=ttl_seconds)
    except Exception:
        logger.warning("Session cache write failed", exc_info=True)


async def invalidate_sessions(token_hashes: list[str] | tuple[str, ...]) -> None:
    keys = [_session_cache_key(token_hash) for token_hash in token_hashes if token_hash]
    if not keys:
        return

    try:
        client = await get_redis()
        await client.delete(*keys)
    except Exception:
        logger.warning("Session cache delete failed", exc_info=True)


def schedule_cache_session(
    session: AsyncSession,
    token_hash: str,
    user_id: int,
    expires_at: datetime,
) -> None:
    operations = session.info.setdefault(_PENDING_SESSION_CACHE_OPS_KEY, [])
    operations.append(
        SessionCacheUpsert(token_hash=token_hash, user_id=user_id, expires_at=expires_at)
    )


def schedule_invalidate_sessions(
    session: AsyncSession,
    token_hashes: list[str] | tuple[str, ...],
) -> None:
    normalized = tuple(token_hash for token_hash in token_hashes if token_hash)
    if not normalized:
        return
    operations = session.info.setdefault(_PENDING_SESSION_CACHE_OPS_KEY, [])
    operations.append(SessionCacheDelete(token_hashes=normalized))


def pop_pending_session_cache_operations(session: AsyncSession) -> list[SessionCacheOperation]:
    operations = session.info.pop(_PENDING_SESSION_CACHE_OPS_KEY, [])
    return list(operations)


async def apply_session_cache_operations(operations: list[SessionCacheOperation]) -> None:
    for operation in operations:
        if isinstance(operation, SessionCacheUpsert):
            await cache_active_session(
                token_hash=operation.token_hash,
                user_id=operation.user_id,
                expires_at=operation.expires_at,
            )
        elif isinstance(operation, SessionCacheDelete):
            await invalidate_sessions(operation.token_hashes)
