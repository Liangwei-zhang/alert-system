from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from domains.auth.repository import UserRepository
from domains.notifications.repository import (
    MessageOutboxRepository,
    NotificationRepository,
    ReceiptRepository,
)
from infra.core.context import RequestContext
from infra.events.outbox import OutboxPublisher


@dataclass(slots=True)
class BridgeAlertResult:
    resolved_user_ids: list[int] = field(default_factory=list)
    skipped_user_ids: list[int] = field(default_factory=list)
    notification_ids: list[str] = field(default_factory=list)
    outbox_ids: list[str] = field(default_factory=list)

    @property
    def created_notifications(self) -> int:
        return len(self.notification_ids)

    @property
    def requested_outbox(self) -> int:
        return len(self.outbox_ids)


class BridgeAlertService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repository = UserRepository(session)
        self.notification_repository = NotificationRepository(session)
        self.receipt_repository = ReceiptRepository(session)
        self.outbox_repository = MessageOutboxRepository(session)
        self.outbox_publisher = OutboxPublisher(session)

    async def send_alert(
        self,
        *,
        context: RequestContext,
        user_ids: list[int],
        title: str,
        body: str,
        channels: list[str],
        notification_type: str,
        ack_required: bool,
        ack_deadline_at: datetime | None,
        signal_id: str | None = None,
        trade_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> BridgeAlertResult:
        normalized_user_ids = self._normalize_user_ids(user_ids)
        rows = await self.user_repository.list_users_by_ids(normalized_user_ids)
        resolved_user_ids = [int(user.id) for user, _account in rows]
        resolved_lookup = set(resolved_user_ids)
        skipped_user_ids = [
            user_id for user_id in normalized_user_ids if user_id not in resolved_lookup
        ]

        payload_metadata = {
            **dict(metadata or {}),
            "bridge_alert": True,
            "request_id": context.request_id,
            "source": "public-api",
        }

        notifications = await self.notification_repository.bulk_create(
            [
                {
                    "user_id": user_id,
                    "signal_id": signal_id,
                    "trade_id": trade_id,
                    "type": notification_type,
                    "title": title,
                    "body": body,
                    "metadata": payload_metadata,
                }
                for user_id in resolved_user_ids
            ]
        )

        outbox_ids: list[str] = []
        for user_id, notification in zip(resolved_user_ids, notifications):
            receipt = await self.receipt_repository.create_receipt(
                notification_id=notification.id,
                user_id=user_id,
                ack_required=ack_required,
                ack_deadline_at=ack_deadline_at,
            )
            outbox_rows = [
                {
                    "notification_id": notification.id,
                    "user_id": user_id,
                    "channel": channel,
                    "payload": {
                        "title": title,
                        "body": body,
                        "subject": title,
                        "notification_type": notification_type,
                        "receipt_id": receipt.id,
                        "metadata": payload_metadata,
                        "url": "/app/notifications",
                        "tag": f"notification-{notification.id}",
                    },
                }
                for channel in channels
            ]
            outbox_items = await self.outbox_repository.bulk_create(outbox_rows)
            for outbox_item in outbox_items:
                outbox_ids.append(str(outbox_item.id))
                await self.outbox_publisher.publish_after_commit(
                    topic="notification.requested",
                    key=outbox_item.id,
                    payload={
                        "outbox_id": outbox_item.id,
                        "notification_id": notification.id,
                        "user_id": user_id,
                        "channel": outbox_item.channel,
                    },
                    headers={"request_id": context.request_id},
                )

        return BridgeAlertResult(
            resolved_user_ids=resolved_user_ids,
            skipped_user_ids=skipped_user_ids,
            notification_ids=[str(notification.id) for notification in notifications],
            outbox_ids=outbox_ids,
        )

    @staticmethod
    def _normalize_user_ids(user_ids: list[int]) -> list[int]:
        seen: set[int] = set()
        normalized: list[int] = []
        for raw_user_id in user_ids:
            user_id = int(raw_user_id)
            if user_id <= 0 or user_id in seen:
                continue
            seen.add(user_id)
            normalized.append(user_id)
        return normalized