from __future__ import annotations

from domains.notifications.repository import NotificationRepository, ReceiptRepository
from infra.core.errors import AppError
from infra.events.outbox import OutboxPublisher


class NotificationCommandService:
    def __init__(
        self,
        notification_repository: NotificationRepository,
        receipt_repository: ReceiptRepository,
    ) -> None:
        self.notification_repository = notification_repository
        self.receipt_repository = receipt_repository
        self.outbox = OutboxPublisher(notification_repository.session)

    async def mark_read(self, user_id: int, notification_id: str) -> None:
        updated = await self.notification_repository.mark_read(user_id, notification_id)
        if not updated:
            raise AppError("notification_not_found", "Notification not found", status_code=404)
        await self.receipt_repository.mark_opened(notification_id, user_id)

    async def mark_all_read(self, user_id: int) -> int:
        notification_ids = await self.notification_repository.mark_all_read(user_id)
        for notification_id in notification_ids:
            await self.receipt_repository.mark_opened(notification_id, user_id)
        return len(notification_ids)

    async def acknowledge(self, user_id: int, notification_id: str):
        updated = await self.notification_repository.mark_read(user_id, notification_id)
        if not updated:
            raise AppError("notification_not_found", "Notification not found", status_code=404)
        receipt = await self.receipt_repository.acknowledge(notification_id, user_id)
        await self.outbox.publish_after_commit(
            topic="notification.acknowledged",
            key=str(user_id),
            payload={"user_id": user_id, "notification_id": notification_id},
        )
        return receipt
