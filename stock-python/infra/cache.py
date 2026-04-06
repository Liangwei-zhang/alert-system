"""
Redis cache client.
"""
import json
from typing import Any, Optional

import redis.asyncio as redis

from infra.config import settings


class CacheClient:
    """Redis cache client for high concurrency."""

    def __init__(self):
        self.client: Optional[redis.Redis] = None

    async def connect(self):
        """Connect to Redis."""
        self.client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.client:
            await self.client.close()

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.client:
            return None
        value = await self.client.get(key)
        if value:
            return json.loads(value)
        return None

    async def set(
        self,
        key: str,
        value: Any,
        expire: int = 300,
    ) -> bool:
        """Set value in cache."""
        if not self.client:
            return False
        return await self.client.set(
            key,
            json.dumps(value),
            ex=expire,
        )

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.client:
            return False
        return await self.client.delete(key) > 0

    async def incr(self, key: str) -> int:
        """Increment counter."""
        if not self.client:
            return 0
        return await self.client.incr(key)


cache = CacheClient()