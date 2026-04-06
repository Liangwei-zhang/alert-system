from __future__ import annotations

from datetime import datetime, timezone

from domains.notifications.command_service import NotificationCommandService
from domains.notifications.push_service import PushSubscriptionService
from domains.notifications.query_service import NotificationQueryService
from domains.notifications.schemas import (
    NotificationItemResponse,
    NotificationListResponse,
    PushDeviceResponse,
)
from domains.notifications.schemas import TestPushResponse as PushTestResponse
from tests.helpers.app_client import PublicApiClient


def test_notification_flow(authenticated_public_api_client: PublicApiClient, monkeypatch) -> None:
    now = datetime(2026, 4, 4, tzinfo=timezone.utc)
    calls: dict[str, object] = {}

    notification_list_response = NotificationListResponse(
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
    push_devices = [
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
    registered_device = PushDeviceResponse(
        id="device-row-2",
        device_id="device-2",
        endpoint="https://push.example/device-2",
        provider="webpush",
        is_active=True,
        last_seen_at=now,
        created_at=now,
    )
    acknowledged_receipt = type("Receipt", (), {"acknowledged_at": now})()

    async def fake_list_notifications(
        self, user_id: int, cursor: str | None, limit: int
    ) -> NotificationListResponse:
        calls["list_notifications"] = {"user_id": user_id, "cursor": cursor, "limit": limit}
        return notification_list_response

    async def fake_list_push_devices(self, user_id: int) -> list[PushDeviceResponse]:
        calls["list_push_devices"] = user_id
        return push_devices

    async def fake_register_device(self, user_id: int, request) -> PushDeviceResponse:
        calls["register_device"] = {"user_id": user_id, "payload": request.model_dump()}
        return registered_device

    async def fake_disable_device(self, user_id: int, device_id: str) -> None:
        calls["disable_device"] = {"user_id": user_id, "device_id": device_id}

    async def fake_send_test_push(self, user_id: int, device_id: str) -> PushTestResponse:
        calls["send_test_push"] = {"user_id": user_id, "device_id": device_id}
        return PushTestResponse(delivered=True, invalidated=False, error=None)

    async def fake_mark_all_read(self, user_id: int) -> int:
        calls["mark_all_read"] = user_id
        return 1

    async def fake_mark_read(self, user_id: int, notification_id: str) -> None:
        calls["mark_read"] = {"user_id": user_id, "notification_id": notification_id}

    async def fake_acknowledge(self, user_id: int, notification_id: str):
        calls["acknowledge"] = {"user_id": user_id, "notification_id": notification_id}
        return acknowledged_receipt

    monkeypatch.setattr(NotificationQueryService, "list_notifications", fake_list_notifications)
    monkeypatch.setattr(NotificationQueryService, "list_push_devices", fake_list_push_devices)
    monkeypatch.setattr(PushSubscriptionService, "register_device", fake_register_device)
    monkeypatch.setattr(PushSubscriptionService, "disable_device", fake_disable_device)
    monkeypatch.setattr(PushSubscriptionService, "send_test_push", fake_send_test_push)
    monkeypatch.setattr(NotificationCommandService, "mark_all_read", fake_mark_all_read)
    monkeypatch.setattr(NotificationCommandService, "mark_read", fake_mark_read)
    monkeypatch.setattr(NotificationCommandService, "acknowledge", fake_acknowledge)

    list_result = authenticated_public_api_client.get(
        "/v1/notifications", params={"cursor": "cursor-1", "limit": 10}
    )
    assert list_result.status_code == 200
    assert list_result.json()["next_cursor"] == "cursor-2"
    assert list_result.json()["items"][0]["id"] == "notif-1"

    list_devices_result = authenticated_public_api_client.get("/v1/notifications/push-devices")
    assert list_devices_result.status_code == 200
    assert list_devices_result.json()[0]["device_id"] == "device-1"

    register_result = authenticated_public_api_client.post(
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
    assert register_result.status_code == 201
    assert register_result.json()["device_id"] == "device-2"

    disable_result = authenticated_public_api_client.delete(
        "/v1/notifications/push-devices/device-2"
    )
    assert disable_result.status_code == 204

    test_push_result = authenticated_public_api_client.post(
        "/v1/notifications/push-devices/device-2/test"
    )
    assert test_push_result.status_code == 200
    assert test_push_result.json() == {"delivered": True, "invalidated": False, "error": None}

    read_all_result = authenticated_public_api_client.put("/v1/notifications/read-all")
    assert read_all_result.status_code == 200
    assert read_all_result.json() == {"message": "All notifications marked as read"}

    mark_read_result = authenticated_public_api_client.put("/v1/notifications/notif-1/read")
    assert mark_read_result.status_code == 200
    assert mark_read_result.json() == {"message": "Notification marked as read"}

    ack_result = authenticated_public_api_client.put("/v1/notifications/notif-1/ack")
    assert ack_result.status_code == 200
    assert ack_result.json() == {
        "message": "Notification acknowledged",
        "acknowledged": True,
        "acknowledged_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    assert calls["list_notifications"] == {"user_id": 42, "cursor": "cursor-1", "limit": 10}
    assert calls["list_push_devices"] == 42
    assert calls["register_device"] == {
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
    assert calls["disable_device"] == {"user_id": 42, "device_id": "device-2"}
    assert calls["send_test_push"] == {"user_id": 42, "device_id": "device-2"}
    assert calls["mark_all_read"] == 42
    assert calls["mark_read"] == {"user_id": 42, "notification_id": "notif-1"}
    assert calls["acknowledge"] == {"user_id": 42, "notification_id": "notif-1"}
