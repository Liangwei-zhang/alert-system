import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from infra.cache.trade_info_cache import (
    apply_trade_info_cache_operations,
    cache_trade_snapshot,
    get_cached_trade_snapshot,
    get_or_load_trade_snapshot,
    pop_pending_trade_info_cache_operations,
    schedule_invalidate_trade_info,
)


class FakeRedisClient:
    def __init__(self) -> None:
        self.storage = {}
        self.deleted = []

    async def get(self, key):
        return self.storage.get(key)

    async def set(self, key, value, ex=None, nx=False):
        del ex
        if nx and key in self.storage:
            return False
        self.storage[key] = value
        return True

    async def exists(self, key):
        return 1 if key in self.storage else 0

    async def eval(self, script, numkeys, *args):
        del script, numkeys
        key, token = args
        if self.storage.get(key) == token:
            self.storage.pop(key, None)
            return 1
        return 0

    async def delete(self, *keys):
        self.deleted.extend(keys)
        for key in keys:
            self.storage.pop(key, None)
        return len(keys)


class FakeSession:
    def __init__(self) -> None:
        self.info = {}


class TradeInfoCacheTest(unittest.TestCase):
    def test_cache_round_trip_uses_redis_payload(self) -> None:
        client = FakeRedisClient()

        async def run_test() -> None:
            with patch(
                "infra.cache.trade_info_cache.get_redis",
                AsyncMock(return_value=client),
            ):
                await cache_trade_snapshot(
                    "trade-42",
                    {"id": "trade-42", "symbol": "AAPL", "status": "pending"},
                    ttl_seconds=30,
                )
                cached = await get_cached_trade_snapshot("trade-42")
            self.assertEqual(cached, {"id": "trade-42", "symbol": "AAPL", "status": "pending"})
            self.assertEqual(json.loads(client.storage["trade:info:v1:trade-42"])["symbol"], "AAPL")

        asyncio.run(run_test())

    def test_get_or_load_coalesces_concurrent_misses(self) -> None:
        client = FakeRedisClient()

        async def run_test() -> None:
            loader_started = asyncio.Event()
            release_loader = asyncio.Event()
            loader_calls = 0

            async def loader() -> dict:
                nonlocal loader_calls
                loader_calls += 1
                loader_started.set()
                await release_loader.wait()
                return {"id": "trade-42", "status": "pending"}

            with (
                patch(
                    "infra.cache.trade_info_cache.get_redis",
                    AsyncMock(return_value=client),
                ),
                patch(
                    "infra.cache.fill_lock.get_redis",
                    AsyncMock(return_value=client),
                ),
            ):
                first = asyncio.create_task(get_or_load_trade_snapshot("trade-42", loader))
                await loader_started.wait()
                second = asyncio.create_task(get_or_load_trade_snapshot("trade-42", loader))
                await asyncio.sleep(0)
                release_loader.set()
                first_payload, second_payload = await asyncio.gather(first, second)

            self.assertEqual(loader_calls, 1)
            self.assertEqual(first_payload, {"id": "trade-42", "status": "pending"})
            self.assertEqual(second_payload, first_payload)
            self.assertEqual(
                json.loads(client.storage["trade:info:v1:trade-42"]),
                {"id": "trade-42", "status": "pending"},
            )

        asyncio.run(run_test())

    def test_get_or_load_uses_remote_fill_when_distributed_lock_is_held(self) -> None:
        client = FakeRedisClient()
        lock_key = "trade:info:v1:trade-42:fill-lock"
        client.storage[lock_key] = "remote-owner"

        async def run_test() -> None:
            loader = AsyncMock()

            async def remote_fill() -> None:
                await asyncio.sleep(0.01)
                client.storage["trade:info:v1:trade-42"] = json.dumps(
                    {"id": "trade-42", "status": "confirmed"}
                )
                client.storage.pop(lock_key, None)

            with (
                patch(
                    "infra.cache.trade_info_cache.get_redis",
                    AsyncMock(return_value=client),
                ),
                patch(
                    "infra.cache.fill_lock.get_redis",
                    AsyncMock(return_value=client),
                ),
                patch(
                    "infra.cache.fill_lock.get_settings",
                    return_value=SimpleNamespace(
                        cache_fill_lock_ttl_seconds=15,
                        cache_fill_lock_wait_timeout_ms=200,
                        cache_fill_lock_poll_interval_ms=5,
                    ),
                ),
            ):
                remote_task = asyncio.create_task(remote_fill())
                payload = await get_or_load_trade_snapshot("trade-42", loader)
                await remote_task

            self.assertEqual(payload, {"id": "trade-42", "status": "confirmed"})
            loader.assert_not_awaited()

        asyncio.run(run_test())

    def test_pending_invalidation_ops_are_deduplicated_on_apply(self) -> None:
        session = FakeSession()
        schedule_invalidate_trade_info(session, "trade-42")
        schedule_invalidate_trade_info(session, ["trade-42", "trade-43"])
        operations = pop_pending_trade_info_cache_operations(session)

        async def run_test() -> None:
            with patch(
                "infra.cache.trade_info_cache.invalidate_trade_snapshots",
                AsyncMock(),
            ) as invalidator:
                await apply_trade_info_cache_operations(operations)
            invalidator.assert_awaited_once_with(("trade-42", "trade-43"))

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
