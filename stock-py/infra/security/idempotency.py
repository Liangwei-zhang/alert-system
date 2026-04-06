from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

from infra.cache.redis_client import get_redis
from infra.core.config import get_settings


class IdempotencyService:
    def __init__(self, redis_client: Redis | None = None, key_prefix: str = "idempotency") -> None:
        self._redis = redis_client
        self.key_prefix = key_prefix

    async def _client(self) -> Redis:
        return self._redis or await get_redis()

    def _lock_key(self, key: str) -> str:
        return f"{self.key_prefix}:lock:{key}"

    def _result_key(self, key: str) -> str:
        return f"{self.key_prefix}:result:{key}"

    async def acquire(self, key: str, ttl_seconds: int | None = None) -> bool:
        client = await self._client()
        ttl = ttl_seconds or get_settings().idempotency_ttl_seconds
        return bool(await client.set(self._lock_key(key), "1", ex=ttl, nx=True))

    async def store_result(
        self,
        key: str,
        result: Any,
        ttl_seconds: int | None = None,
    ) -> None:
        client = await self._client()
        ttl = ttl_seconds or get_settings().idempotency_ttl_seconds
        payload = json.dumps(result)
        await client.set(self._result_key(key), payload, ex=ttl)
        await client.expire(self._lock_key(key), ttl)

    async def replay(self, key: str) -> Any | None:
        client = await self._client()
        raw = await client.get(self._result_key(key))
        return json.loads(raw) if raw else None
