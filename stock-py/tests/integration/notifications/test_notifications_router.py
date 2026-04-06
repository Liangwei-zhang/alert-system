from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.public_api.routers import notifications as notifications_router
from domains.notifications.schemas import (
    NotificationItemResponse,
    NotificationListResponse,
    PushDeviceResponse,
)
from domains.notifications.schemas import TestPushResponse as PushTestResponse
from infra.security.auth import CurrentUser, require_user


class FakeNotificationQueryService:
    notifications_response = None
    push_devices_response = []
    calls: dict[str, list] = {}

    @classmethod
    def reset(cls) -> None:
        cls.calls = {"list_notifications": [], "list_push_devices": []}

    async def list_notifications(self, user_id: int, cursor: str | None, limit: int):
        self.calls["list_notifications"].append(
            {"user_id": user_id, "cursor": cursor, "limit": limit}
        )
        return self.notifications_response

    async def list_push_devices(self, user_id: int):
        self.calls["list_push_devices"].append(user_id)
        return self.push_devices_response


class FakeNotificationCommandService:
    acknowledge_response = None
    calls: dict[str, list] = {}

    @classmethod
    def reset(cls) -> None:
        cls.calls = {"mark_all_read": [], "mark_read": [], "acknowledge": []}

    async def mark_all_read(self, user_id: int):
        self.calls["mark_all_read"].append(user_id)

    async def mark_read(self, user_id: int, notification_id: str):
        self.calls["mark_read"].append({"user_id": user_id, "notification_id": notification_id})

    async def acknowledge(self, user_id: int, notification_id: str):
        self.calls["acknowledge"].append({"user_id": user_id, "notification_id": notification_id})
        return self.acknowledge_response


class FakePushSubscriptionService:
    register_response = None
    test_response = None
    calls: dict[str, list] = {}

    @classmethod
    def reset(cls) -> None:
        cls.calls = {"register_device": [], "disable_device": [], "send_test_push": []}

    async def register_device(self, user_id: int, data):
        self.calls["register_device"].append({"user_id": user_id, "payload": data.model_dump()})
        return self.register_response

    async def disable_device(self, user_id: int, device_id: str):
        self.calls["disable_device"].append({"user_id": user_id, "device_id": device_id})

    async def send_test_push(self, user_id: int, device_id: str):
        self.calls["send_test_push"].append({"user_id": user_id, "device_id": device_id})
        return self.test_response


class NotificationsRouterIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        FakeNotificationQueryService.reset()
        FakeNotificationCommandService.reset()
        FakePushSubscriptionService.reset()

        self.query_service = FakeNotificationQueryService()
        self.command_service = FakeNotificationCommandService()
        self.push_service = FakePushSubscriptionService()

        self.app = FastAPI()
        self.app.include_router(notifications_router.router, prefix="/v1")

        async def override_require_user():
            return CurrentUser(user_id=42, plan="pro", scopes=["app"], is_admin=False)

        async def override_db_session():
            yield object()

        self.app.dependency_overrides[require_user] = override_require_user
        self.app.dependency_overrides[notifications_router.get_db_session] = override_db_session

        self.query_patch = patch.object(
            notifications_router, "_query_service", lambda _session: self.query_service
        )
        self.command_patch = patch.object(
            notifications_router, "_command_service", lambda _session: self.command_service
        )
        self.push_patch = patch.object(
            notifications_router, "_push_service", lambda _session: self.push_service
        )
        self.query_patch.start()
        self.command_patch.start()
        self.push_patch.start()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.query_patch.stop()
        self.command_patch.stop()
        self.push_patch.stop()

    def test_notifications_router_returns_list_devices_and_command_results(self) -> None:
        now = datetime(2026, 4, 5, tzinfo=timezone.utc)
        FakeNotificationQueryService.notifications_response = NotificationListResponse(
            items=[
                NotificationItemResponse(
                    id="notif-1",
                    signal_id="signal-1",
                    trade_id=None,
                    type="signal.generated",
                    title="Buy signal: AAPL",
                    body="Buy opportunity detected.",
                    is_read=False,
                    created_at=now,
                    receipt_id="receipt-1",
                    ack_required=True,
                    ack_deadline_at=now,
                    opened_at=None,
                    acknowledged_at=None,
                    last_delivery_channel="push",
                    last_delivery_status="delivered",
                    escalation_level=0,
                )
            ],
            next_cursor="cursor-2",
        )
        FakeNotificationQueryService.push_devices_response = [
            PushDeviceResponse(
                id="device-row-1",
                device_id="device-1",
                endpoint="https://push.example/device-1",
                provider="webpush",
                is_active=True,
                last_seen_at=now,
                created_at=now,
            )
        ]
        FakePushSubscriptionService.register_response = PushDeviceResponse(
            id="device-row-2",
            device_id="device-2",
            endpoint="https://push.example/device-2",
            provider="webpush",
            is_active=True,
            last_seen_at=now,
            created_at=now,
        )
        FakePushSubscriptionService.test_response = PushTestResponse(
            delivered=True,
            invalidated=False,
            error=None,
        )
        FakeNotificationCommandService.acknowledge_response = type(
            "Receipt", (), {"acknowledged_at": now}
        )()

        list_response = self.client.get(
            "/v1/notifications", params={"cursor": "cursor-1", "limit": 10}
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(
            list_response.json(),
            {
                "items": [
                    {
                        "id": "notif-1",
                        "signal_id": "signal-1",
                        "trade_id": None,
                        "type": "signal.generated",
                        "title": "Buy signal: AAPL",
                        "body": "Buy opportunity detected.",
                        "is_read": False,
                        "created_at": "2026-04-05T00:00:00Z",
                        "receipt_id": "receipt-1",
                        "ack_required": True,
                        "ack_deadline_at": "2026-04-05T00:00:00Z",
                        "opened_at": None,
                        "acknowledged_at": None,
                        "last_delivery_channel": "push",
                        "last_delivery_status": "delivered",
                        "escalation_level": 0,
                    }
                ],
                "next_cursor": "cursor-2",
            },
        )

        devices_response = self.client.get("/v1/notifications/push-devices")
        self.assertEqual(devices_response.status_code, 200)
        self.assertEqual(
            devices_response.json(),
            [
                {
                    "id": "device-row-1",
                    "device_id": "device-1",
                    "endpoint": "https://push.example/device-1",
                    "provider": "webpush",
                    "is_active": True,
                    "last_seen_at": "2026-04-05T00:00:00Z",
                    "created_at": "2026-04-05T00:00:00Z",
                }
            ],
        )

        register_response = self.client.post(
            "/v1/notifications/push-devices",
            json={
                "device_id": "device-2",
                "endpoint": "https://push.example/device-2",
                "provider": "webpush",
                "public_key": "pk",
                "auth_key": "ak",
                "user_agent": "pytest",
                "locale": "en-US",
                "timezone": "UTC",
                "extra": {"platform": "web"},
            },
        )
        self.assertEqual(register_response.status_code, 201)
        self.assertEqual(
            register_response.json(),
            {
                "id": "device-row-2",
                "device_id": "device-2",
                "endpoint": "https://push.example/device-2",
                "provider": "webpush",
                "is_active": True,
                "last_seen_at": "2026-04-05T00:00:00Z",
                "created_at": "2026-04-05T00:00:00Z",
            },
        )

        disable_response = self.client.delete("/v1/notifications/push-devices/device-2")
        self.assertEqual(disable_response.status_code, 204)

        test_response = self.client.post("/v1/notifications/push-devices/device-2/test")
        self.assertEqual(test_response.status_code, 200)
        self.assertEqual(
            test_response.json(),
            {"delivered": True, "invalidated": False, "error": None},
        )

        read_all_response = self.client.put("/v1/notifications/read-all")
        self.assertEqual(read_all_response.status_code, 200)
        self.assertEqual(read_all_response.json(), {"message": "All notifications marked as read"})

        read_response = self.client.put("/v1/notifications/notif-1/read")
        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(read_response.json(), {"message": "Notification marked as read"})

        acknowledge_response = self.client.put("/v1/notifications/notif-1/ack")
        self.assertEqual(acknowledge_response.status_code, 200)
        self.assertEqual(
            acknowledge_response.json(),
            {
                "message": "Notification acknowledged",
                "acknowledged": True,
                "acknowledged_at": "2026-04-05T00:00:00Z",
            },
        )

        self.assertEqual(
            FakeNotificationQueryService.calls["list_notifications"],
            [{"user_id": 42, "cursor": "cursor-1", "limit": 10}],
        )
        self.assertEqual(FakeNotificationQueryService.calls["list_push_devices"], [42])
        self.assertEqual(
            FakePushSubscriptionService.calls["register_device"],
            [
                {
                    "user_id": 42,
                    "payload": {
                        "device_id": "device-2",
                        "endpoint": "https://push.example/device-2",
                        "provider": "webpush",
                        "public_key": "pk",
                        "auth_key": "ak",
                        "user_agent": "pytest",
                        "locale": "en-US",
                        "timezone": "UTC",
                        "extra": {"platform": "web"},
                    },
                }
            ],
        )
        self.assertEqual(
            FakePushSubscriptionService.calls["disable_device"],
            [{"user_id": 42, "device_id": "device-2"}],
        )
        self.assertEqual(
            FakePushSubscriptionService.calls["send_test_push"],
            [{"user_id": 42, "device_id": "device-2"}],
        )
        self.assertEqual(FakeNotificationCommandService.calls["mark_all_read"], [42])
        self.assertEqual(
            FakeNotificationCommandService.calls["mark_read"],
            [{"user_id": 42, "notification_id": "notif-1"}],
        )
        self.assertEqual(
            FakeNotificationCommandService.calls["acknowledge"],
            [{"user_id": 42, "notification_id": "notif-1"}],
        )


if __name__ == "__main__":
    unittest.main()
