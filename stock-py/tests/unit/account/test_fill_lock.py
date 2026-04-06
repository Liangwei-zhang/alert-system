import asyncio
import unittest
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from infra.cache.fill_lock import (
    release_cache_fill_lock,
    start_cache_fill_lock_renewal,
    stop_cache_fill_lock_renewal,
    try_acquire_cache_fill_lock,
)


class ExpiringFakeRedisClient:
    def __init__(self) -> None:
        self.storage = {}
        self.expirations = {}
        self.eval_calls = []

    def _prune_expired(self, key=None) -> None:
        now = perf_counter()
        keys = [key] if key is not None else list(self.expirations)
        for current_key in keys:
            deadline = self.expirations.get(current_key)
            if deadline is not None and deadline <= now:
                self.storage.pop(current_key, None)
                self.expirations.pop(current_key, None)

    async def get(self, key):
        self._prune_expired(key)
        return self.storage.get(key)

    async def set(self, key, value, ex=None, nx=False):
        self._prune_expired(key)
        if nx and key in self.storage:
            return False
        self.storage[key] = value
        if ex is not None:
            self.expirations[key] = perf_counter() + float(ex)
        return True

    async def exists(self, key):
        self._prune_expired(key)
        return 1 if key in self.storage else 0

    async def eval(self, script, numkeys, *args):
        del numkeys
        self.eval_calls.append({"script": script, "args": args})
        if len(args) == 2:
            key, token = args
            self._prune_expired(key)
            if self.storage.get(key) == token:
                self.storage.pop(key, None)
                self.expirations.pop(key, None)
                return 1
            return 0

        key, token, ttl_seconds = args
        self._prune_expired(key)
        if self.storage.get(key) == token:
            self.expirations[key] = perf_counter() + float(ttl_seconds)
            return 1
        return 0


class FillLockTest(unittest.TestCase):
    def test_lock_renewal_keeps_long_running_fill_owned(self) -> None:
        client = ExpiringFakeRedisClient()

        async def run_test() -> None:
            with (
                patch(
                    "infra.cache.fill_lock.get_redis",
                    AsyncMock(return_value=client),
                ),
                patch(
                    "infra.cache.fill_lock.get_settings",
                    return_value=SimpleNamespace(
                        cache_fill_lock_ttl_seconds=1,
                        cache_fill_lock_wait_timeout_ms=200,
                        cache_fill_lock_poll_interval_ms=5,
                        cache_fill_lock_refresh_interval_ms=200,
                    ),
                ),
            ):
                first = await try_acquire_cache_fill_lock("cache:key", "test_cache")
                self.assertEqual(first.status, "acquired")
                renewal_task = start_cache_fill_lock_renewal(
                    "cache:key",
                    first.token,
                    "test_cache",
                )

                await asyncio.sleep(1.3)
                second = await try_acquire_cache_fill_lock("cache:key", "test_cache")
                self.assertEqual(second.status, "contended")
                self.assertTrue(any(len(call["args"]) == 3 for call in client.eval_calls))

                await stop_cache_fill_lock_renewal(renewal_task)
                await release_cache_fill_lock("cache:key", first.token, "test_cache")
                third = await try_acquire_cache_fill_lock("cache:key", "test_cache")
                self.assertEqual(third.status, "acquired")

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
