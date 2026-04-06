from __future__ import annotations

from domains.notifications.repository import (
    NotificationRepository,
    PushSubscriptionRepository,
    ReceiptRepository,
)
from domains.notifications.schemas import (
    NotificationItemResponse,
    NotificationListResponse,
    PushDeviceResponse,
)
from infra.cache.push_devices_cache import get_or_load_push_devices


class NotificationQueryService:
    def __init__(
        self,
        notification_repository: NotificationRepository,
        push_subscription_repository: PushSubscriptionRepository,
        receipt_repository: ReceiptRepository,
    ) -> None:
        self.notification_repository = notification_repository
        self.push_subscription_repository = push_subscription_repository
        self.receipt_repository = receipt_repository

    async def _build_push_device_payloads(self, user_id: int) -> list[dict]:
        devices = await self.push_subscription_repository.list_active_devices(user_id)
        return [
            PushDeviceResponse(
                id=device.id,
                device_id=device.device_id,
                endpoint=device.endpoint,
                provider=device.provider,
                is_active=device.is_active,
                last_seen_at=device.last_seen_at,
                created_at=device.created_at,
            ).model_dump(mode="json")
            for device in devices
        ]

    async def list_notifications(
        self, user_id: int, cursor: str | None, limit: int
    ) -> NotificationListResponse:
        notifications, next_cursor = await self.notification_repository.list_page(
            user_id, limit, cursor
        )
        receipts = await self.receipt_repository.list_latest_receipts(
            [notification.id for notification in notifications],
            user_id,
        )
        items: list[NotificationItemResponse] = []
        for notification in notifications:
            receipt = receipts.get(notification.id)
            items.append(
                NotificationItemResponse(
                    id=notification.id,
                    signal_id=notification.signal_id,
                    trade_id=notification.trade_id,
                    type=notification.type,
                    title=notification.title,
                    body=notification.body,
                    is_read=notification.is_read,
                    created_at=notification.created_at,
                    receipt_id=getattr(receipt, "id", None),
                    ack_required=bool(getattr(receipt, "ack_required", False)),
                    ack_deadline_at=getattr(receipt, "ack_deadline_at", None),
                    opened_at=getattr(receipt, "opened_at", None),
                    acknowledged_at=getattr(receipt, "acknowledged_at", None),
                    last_delivery_channel=getattr(receipt, "last_delivery_channel", None),
                    last_delivery_status=getattr(receipt, "last_delivery_status", None),
                    escalation_level=int(getattr(receipt, "escalation_level", 0) or 0),
                )
            )
        return NotificationListResponse(items=items, next_cursor=next_cursor)

    async def list_push_devices(self, user_id: int) -> list[PushDeviceResponse]:
        payloads = await get_or_load_push_devices(
            user_id,
            lambda: self._build_push_device_payloads(user_id),
        )
        return [PushDeviceResponse.model_validate(payload) for payload in payloads]
