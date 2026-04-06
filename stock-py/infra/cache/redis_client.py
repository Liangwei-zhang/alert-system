from __future__ import annotations

import asyncio
import json
from typing import Any

import redis.asyncio as redis
from redis.asyncio import Redis

from infra.core.config import get_settings

_redis_client: Redis | None = None
_redis_lock = asyncio.Lock()


async def get_redis() -> Redis:
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    async with _redis_lock:
        if _redis_client is None:
            settings = get_settings()
            _redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )

    return _redis_client


async def close_redis() -> None:
    global _redis_client

    if _redis_client is None:
        return

    close = getattr(_redis_client, "aclose", None)
    if close is not None:
        await close()
    else:
        await _redis_client.close()

    _redis_client = None


async def get_json(key: str) -> Any | None:
    client = await get_redis()
    value = await client.get(key)
    return json.loads(value) if value else None


async def set_json(key: str, value: Any, expire: int | None = None) -> None:
    client = await get_redis()
    await client.set(key, json.dumps(value), ex=expire)
