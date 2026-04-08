from __future__ import annotations

import json

from domains.notifications.repository import DeliveryAttemptRepository, PushSubscriptionRepository
from domains.notifications.schemas import (
    PushDeviceResponse,
    RegisterPushDeviceRequest,
    TestPushResponse,
)
from infra.cache.push_devices_cache import schedule_invalidate_push_devices
from infra.core.config import get_settings
from infra.core.errors import AppError
from infra.security.webpush import load_vapid_private_key


class PushSubscriptionService:
    def __init__(
        self,
        push_subscription_repository: PushSubscriptionRepository,
        delivery_attempt_repository: DeliveryAttemptRepository,
    ) -> None:
        self.push_subscription_repository = push_subscription_repository
        self.delivery_attempt_repository = delivery_attempt_repository

    def _schedule_push_devices_invalidation(self, user_id: int) -> None:
        schedule_invalidate_push_devices(
            getattr(self.push_subscription_repository, "session", None),
            user_id,
        )

    async def register_device(
        self,
        user_id: int,
        request: RegisterPushDeviceRequest,
    ) -> PushDeviceResponse:
        device = await self.push_subscription_repository.upsert_device(
            user_id, request.model_dump()
        )
        self._schedule_push_devices_invalidation(user_id)
        return PushDeviceResponse(
            id=device.id,
            device_id=device.device_id,
            endpoint=device.endpoint,
            provider=device.provider,
            is_active=device.is_active,
            last_seen_at=device.last_seen_at,
            created_at=device.created_at,
        )

    async def disable_device(self, user_id: int, device_id: str) -> None:
        device = await self.push_subscription_repository.disable_device(user_id, device_id)
        if device is None:
            raise AppError("push_device_not_found", "Push subscription not found", status_code=404)
        self._schedule_push_devices_invalidation(user_id)

    async def send_test_push(self, user_id: int, device_id: str) -> TestPushResponse:
        device = await self.push_subscription_repository.get_device(user_id, device_id)
        if device is None or not device.is_active:
            raise AppError("push_device_not_found", "Push subscription not found", status_code=404)

        attempt = await self.delivery_attempt_repository.record_attempt(
            channel="push",
            status="pending",
            notification_id=None,
        )

        if device.provider != "webpush":
            await self.delivery_attempt_repository.mark_failure(attempt, "provider_not_implemented")
            return TestPushResponse(delivered=False, error="provider_not_implemented")

        settings = get_settings()
        if not settings.web_push_public_key or not settings.web_push_private_key:
            await self.delivery_attempt_repository.mark_failure(attempt, "web-push-not-configured")
            return TestPushResponse(delivered=False, error="web-push-not-configured")

        try:
            from pywebpush import WebPushException, webpush
        except ImportError:
            await self.delivery_attempt_repository.mark_failure(attempt, "pywebpush_not_installed")
            return TestPushResponse(delivered=False, error="pywebpush_not_installed")

        try:
            webpush(
                subscription_info={
                    "endpoint": device.endpoint,
                    "keys": {
                        "p256dh": device.public_key or "",
                        "auth": device.auth_key or "",
                    },
                },
                data=json.dumps(
                    {
                        "title": "Stock 測試推送",
                        "body": "這台裝置已可接收即時提醒。",
                        "url": "/app/notifications",
                        "tag": f"push-test-{device.device_id}",
                    }
                ),
                vapid_private_key=load_vapid_private_key(settings.web_push_private_key),
                vapid_claims={"sub": settings.web_push_subject},
            )
        except WebPushException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code in (404, 410):
                await self.push_subscription_repository.disable_device(user_id, device_id)
                self._schedule_push_devices_invalidation(user_id)
                await self.delivery_attempt_repository.mark_failure(
                    attempt, f"webpush_invalid_{status_code}"
                )
                return TestPushResponse(
                    delivered=False,
                    invalidated=True,
                    error=f"webpush_invalid_{status_code}",
                )
            await self.delivery_attempt_repository.mark_failure(attempt, str(exc))
            return TestPushResponse(delivered=False, error=str(exc))
        except Exception as exc:
            await self.delivery_attempt_repository.mark_failure(attempt, str(exc))
            return TestPushResponse(delivered=False, error=str(exc))

        device.last_seen_at = utcnow()
        await self.push_subscription_repository.session.flush()
        await self.delivery_attempt_repository.mark_success(attempt)
        return TestPushResponse(delivered=True)


def utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
