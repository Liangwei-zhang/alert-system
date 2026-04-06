import asyncio
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from domains.notifications.query_service import NotificationQueryService


class FakeNotificationRepository:
    def __init__(self, notifications, next_cursor=None) -> None:
        self.notifications = notifications
        self.next_cursor = next_cursor
        self.calls = []

    async def list_page(self, user_id: int, limit: int, cursor: str | None = None):
        self.calls.append({"user_id": user_id, "limit": limit, "cursor": cursor})
        return self.notifications, self.next_cursor


class FakePushSubscriptionRepository:
    def __init__(self, devices=None) -> None:
        self.devices = list(devices or [])
        self.calls = []

    async def list_active_devices(self, user_id: int):
        self.calls.append(user_id)
        return list(self.devices)


class FakeReceiptRepository:
    def __init__(self, receipts_by_notification) -> None:
        self.receipts_by_notification = receipts_by_notification
        self.batch_calls = []
        self.single_calls = []

    async def list_latest_receipts(self, notification_ids, user_id: int):
        self.batch_calls.append({"notification_ids": list(notification_ids), "user_id": user_id})
        return {
            notification_id: self.receipts_by_notification[notification_id]
            for notification_id in notification_ids
            if notification_id in self.receipts_by_notification
        }

    async def get_latest_receipt(self, notification_id: str, user_id: int):
        self.single_calls.append({"notification_id": notification_id, "user_id": user_id})
        raise AssertionError("NotificationQueryService should batch latest receipt lookups")


class NotificationQueryServiceTest(unittest.TestCase):
    def test_list_notifications_batches_latest_receipts(self) -> None:
        now = datetime(2026, 4, 4, tzinfo=timezone.utc)
        notifications = [
            SimpleNamespace(
                id="n-1",
                signal_id="s-1",
                trade_id="t-1",
                type="signal",
                title="Buy signal",
                body="AAPL setup ready",
                is_read=False,
                created_at=now,
            ),
            SimpleNamespace(
                id="n-2",
                signal_id=None,
                trade_id=None,
                type="system",
                title="Digest",
                body="Summary",
                is_read=True,
                created_at=now,
            ),
        ]
        notification_repository = FakeNotificationRepository(notifications, next_cursor="cursor-2")
        receipt_repository = FakeReceiptRepository(
            {
                "n-1": SimpleNamespace(
                    id="r-1",
                    ack_required=True,
                    ack_deadline_at=now,
                    opened_at=None,
                    acknowledged_at=None,
                    last_delivery_channel="push",
                    last_delivery_status="sent",
                    escalation_level=2,
                )
            }
        )
        service = NotificationQueryService(
            notification_repository=notification_repository,
            push_subscription_repository=FakePushSubscriptionRepository(),
            receipt_repository=receipt_repository,
        )

        response = asyncio.run(service.list_notifications(user_id=42, cursor="cursor-1", limit=10))

        self.assertEqual(
            notification_repository.calls, [{"user_id": 42, "limit": 10, "cursor": "cursor-1"}]
        )
        self.assertEqual(
            receipt_repository.batch_calls,
            [{"notification_ids": ["n-1", "n-2"], "user_id": 42}],
        )
        self.assertEqual(receipt_repository.single_calls, [])
        self.assertEqual(response.next_cursor, "cursor-2")
        self.assertEqual(response.items[0].receipt_id, "r-1")
        self.assertTrue(response.items[0].ack_required)
        self.assertEqual(response.items[0].last_delivery_channel, "push")
        self.assertEqual(response.items[0].escalation_level, 2)
        self.assertIsNone(response.items[1].receipt_id)
        self.assertFalse(response.items[1].ack_required)

    def test_list_push_devices_uses_cached_payload_loader(self) -> None:
        push_repository = FakePushSubscriptionRepository()
        service = NotificationQueryService(
            notification_repository=FakeNotificationRepository([]),
            push_subscription_repository=push_repository,
            receipt_repository=FakeReceiptRepository({}),
        )
        cached_payload = [
            {
                "id": "device-row-1",
                "device_id": "device-1",
                "endpoint": "https://push.example/device-1",
                "provider": "webpush",
                "is_active": True,
                "last_seen_at": "2026-04-05T00:00:00Z",
                "created_at": "2026-04-05T00:00:00Z",
            }
        ]

        with patch(
            "domains.notifications.query_service.get_or_load_push_devices",
            AsyncMock(return_value=cached_payload),
        ) as cache_loader:
            response = asyncio.run(service.list_push_devices(user_id=42))

        cache_loader.assert_awaited_once()
        self.assertEqual(push_repository.calls, [])
        self.assertEqual(response[0].device_id, "device-1")


if __name__ == "__main__":
    unittest.main()
