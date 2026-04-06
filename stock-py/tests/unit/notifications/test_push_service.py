import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from domains.notifications.push_service import PushSubscriptionService
from domains.notifications.schemas import RegisterPushDeviceRequest
from infra.core.errors import AppError


def _device(device_id: str = "device-1") -> SimpleNamespace:
    return SimpleNamespace(
        id=f"row-{device_id}",
        device_id=device_id,
        endpoint=f"https://push.example/{device_id}",
        provider="webpush",
        is_active=True,
        last_seen_at="2026-04-05T00:00:00Z",
        created_at="2026-04-05T00:00:00Z",
        public_key="pk",
        auth_key="ak",
    )


class PushSubscriptionServiceTest(unittest.TestCase):
    def test_register_device_schedules_push_devices_invalidation(self) -> None:
        repository = SimpleNamespace(
            session=SimpleNamespace(info={}),
            upsert_device=AsyncMock(return_value=_device()),
        )
        service = PushSubscriptionService(
            push_subscription_repository=repository,
            delivery_attempt_repository=SimpleNamespace(),
        )

        with patch(
            "domains.notifications.push_service.schedule_invalidate_push_devices"
        ) as invalidator:
            response = asyncio.run(
                service.register_device(
                    42,
                    RegisterPushDeviceRequest(
                        device_id="device-1",
                        endpoint="https://push.example/device-1",
                        provider="webpush",
                    ),
                )
            )

        invalidator.assert_called_once_with(repository.session, 42)
        self.assertEqual(response.device_id, "device-1")

    def test_disable_device_schedules_push_devices_invalidation(self) -> None:
        repository = SimpleNamespace(
            session=SimpleNamespace(info={}),
            disable_device=AsyncMock(return_value=_device()),
        )
        service = PushSubscriptionService(
            push_subscription_repository=repository,
            delivery_attempt_repository=SimpleNamespace(),
        )

        with patch(
            "domains.notifications.push_service.schedule_invalidate_push_devices"
        ) as invalidator:
            asyncio.run(service.disable_device(42, "device-1"))

        invalidator.assert_called_once_with(repository.session, 42)

    def test_disable_device_raises_when_missing(self) -> None:
        repository = SimpleNamespace(
            session=SimpleNamespace(info={}),
            disable_device=AsyncMock(return_value=None),
        )
        service = PushSubscriptionService(
            push_subscription_repository=repository,
            delivery_attempt_repository=SimpleNamespace(),
        )

        with self.assertRaises(AppError):
            asyncio.run(service.disable_device(42, "device-1"))


if __name__ == "__main__":
    unittest.main()
