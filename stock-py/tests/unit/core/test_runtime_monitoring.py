from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from infra.observability import runtime_monitoring


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        del ex
        self.values[key] = value

    async def sadd(self, key: str, *values: str) -> None:
        members = self.sets.setdefault(key, set())
        members.update(values)

    async def smembers(self, key: str) -> set[str]:
        return set(self.sets.get(key, set()))

    async def srem(self, key: str, *values: str) -> None:
        members = self.sets.setdefault(key, set())
        for value in values:
            members.discard(value)


class RuntimeMonitoringTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.redis = FakeRedis()

        async def fake_get_redis() -> FakeRedis:
            return self.redis

        async def fake_get_json(key: str):
            payload = self.redis.values.get(key)
            if payload is None:
                return None
            return json.loads(payload)

        self.get_redis_patch = patch.object(runtime_monitoring, "get_redis", fake_get_redis)
        self.get_json_patch = patch.object(runtime_monitoring, "get_json", fake_get_json)
        self.get_redis_patch.start()
        self.get_json_patch.start()

    async def asyncTearDown(self) -> None:
        self.get_redis_patch.stop()
        self.get_json_patch.stop()

    async def test_list_runtime_components_merges_expected_components(self) -> None:
        await runtime_monitoring.record_runtime_snapshot(
            "scheduler",
            "scheduler",
            "running",
            metadata={"mode": "continuous"},
            ttl_seconds=30,
        )

        components = await runtime_monitoring.list_runtime_components()
        scheduler = next(
            component
            for component in components
            if component["component_kind"] == "scheduler"
            and component["component_name"] == "scheduler"
        )
        missing_worker = next(
            component
            for component in components
            if component["component_kind"] == "worker"
            and component["component_name"] == "event-pipeline"
        )

        self.assertEqual(scheduler["status"], "running")
        self.assertEqual(scheduler["health"], "healthy")
        self.assertEqual(scheduler["metadata"], {"mode": "continuous"})
        self.assertEqual(missing_worker["status"], "missing")
        self.assertEqual(missing_worker["health"], "missing")

    async def test_run_runtime_monitored_records_success_result(self) -> None:
        async def runner() -> dict[str, int]:
            return {"processed": 3}

        result = await runtime_monitoring.run_runtime_monitored(
            "receipt-escalation",
            "worker",
            runner,
            metadata={"mode": "batch"},
            final_status="completed",
        )
        component = await runtime_monitoring.get_runtime_component("worker", "receipt-escalation")

        self.assertEqual(result, {"processed": 3})
        self.assertIsNotNone(component)
        self.assertEqual(component["status"], "completed")
        self.assertEqual(component["metadata"]["last_result"], {"processed": 3})

    async def test_run_runtime_monitored_records_failure(self) -> None:
        async def runner() -> None:
            raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            await runtime_monitoring.run_runtime_monitored(
                "scanner",
                "worker",
                runner,
                metadata={"mode": "batch"},
                final_status="completed",
            )

        component = await runtime_monitoring.get_runtime_component("worker", "scanner")
        self.assertIsNotNone(component)
        self.assertEqual(component["status"], "failed")
        self.assertIn("RuntimeError: boom", component["metadata"]["error"])


if __name__ == "__main__":
    unittest.main()
