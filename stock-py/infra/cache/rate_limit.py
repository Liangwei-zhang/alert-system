from __future__ import annotations

from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis

from infra.cache.redis_client import get_redis


class RedisRateLimiter:
    def __init__(self, redis_client: Redis | None = None, key_prefix: str = "rate-limit") -> None:
        self._redis = redis_client
        self.key_prefix = key_prefix

    async def _client(self) -> Redis:
        return self._redis or await get_redis()

    def _key(self, key: str) -> str:
        return f"{self.key_prefix}:{key}"

    async def hit(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        client = await self._client()
        namespaced_key = self._key(key)
        count = await client.incr(namespaced_key)
        if count == 1:
            await client.expire(namespaced_key, window_seconds)
        return count <= limit

    async def remaining(self, key: str, limit: int) -> int:
        client = await self._client()
        namespaced_key = self._key(key)
        current = await client.get(namespaced_key)
        count = int(current) if current is not None else 0
        return max(limit - count, 0)

    async def reset_at(self, key: str) -> datetime | None:
        client = await self._client()
        ttl = await client.ttl(self._key(key))
        if ttl is None or ttl < 0:
            return None
        return datetime.now(timezone.utc) + timedelta(seconds=ttl)
