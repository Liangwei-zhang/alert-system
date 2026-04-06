from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from infra.core.pagination import decode_cursor, encode_cursor
from infra.db.models.notifications import (
    DeliveryAttemptModel,
    MessageOutboxModel,
    MessageReceiptArchiveModel,
    MessageReceiptModel,
    NotificationModel,
    PushSubscriptionModel,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_trade(self, user_id: int, trade_id: str) -> list[NotificationModel]:
        result = await self.session.execute(
            select(NotificationModel)
            .where(
                NotificationModel.user_id == user_id,
                NotificationModel.trade_id == trade_id,
            )
            .order_by(NotificationModel.created_at.desc(), NotificationModel.id.desc())
        )
        return list(result.scalars().all())

    async def list_ids_by_trade(self, user_id: int, trade_id: str) -> list[str]:
        result = await self.session.execute(
            select(NotificationModel.id)
            .where(
                NotificationModel.user_id == user_id,
                NotificationModel.trade_id == trade_id,
            )
            .order_by(NotificationModel.created_at.desc(), NotificationModel.id.desc())
        )
        return [str(notification_id) for notification_id in result.scalars().all()]

    async def list_page(
        self,
        user_id: int,
        limit: int,
        cursor: str | None = None,
    ) -> tuple[list[NotificationModel], str | None]:
        stmt = (
            select(NotificationModel)
            .where(NotificationModel.user_id == user_id)
            .order_by(NotificationModel.created_at.desc(), NotificationModel.id.desc())
        )

        if cursor:
            payload = decode_cursor(cursor)
            created_at = datetime.fromisoformat(str(payload["created_at"]))
            notification_id = str(payload["id"])
            stmt = stmt.where(
                or_(
                    NotificationModel.created_at < created_at,
                    (
                        (NotificationModel.created_at == created_at)
                        & (NotificationModel.id < notification_id)
                    ),
                )
            )

        result = await self.session.execute(stmt.limit(limit + 1))
        items = list(result.scalars().all())
        next_cursor = None
        if len(items) > limit:
            next_item = items[limit - 1]
            next_cursor = encode_cursor(
                {"created_at": next_item.created_at.isoformat(), "id": next_item.id}
            )
            items = items[:limit]
        return items, next_cursor

    async def get_by_id(self, user_id: int, notification_id: str) -> NotificationModel | None:
        result = await self.session.execute(
            select(NotificationModel).where(
                NotificationModel.id == notification_id,
                NotificationModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def mark_read(self, user_id: int, notification_id: str) -> bool:
        notification = await self.get_by_id(user_id, notification_id)
        if notification is None:
            return False
        notification.is_read = True
        await self.session.flush()
        return True

    async def mark_all_read(self, user_id: int) -> list[str]:
        result = await self.session.execute(
            select(NotificationModel).where(
                NotificationModel.user_id == user_id,
                NotificationModel.is_read.is_(False),
            )
        )
        notifications = list(result.scalars().all())
        notification_ids = [notification.id for notification in notifications]
        for notification in notifications:
            notification.is_read = True
        await self.session.flush()
        return notification_ids

    async def bulk_create(self, rows: list[dict[str, Any]]) -> list[NotificationModel]:
        items = []
        for row in rows:
            payload = dict(row)
            if "metadata" in payload and "metadata_" not in payload:
                payload["metadata_"] = payload.pop("metadata")
            items.append(NotificationModel(**payload))
        self.session.add_all(items)
        await self.session.flush()
        return items


class PushSubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active_devices(self, user_id: int) -> list[PushSubscriptionModel]:
        result = await self.session.execute(
            select(PushSubscriptionModel)
            .where(
                PushSubscriptionModel.user_id == user_id,
                PushSubscriptionModel.is_active.is_(True),
            )
            .order_by(
                PushSubscriptionModel.last_seen_at.desc(), PushSubscriptionModel.created_at.desc()
            )
        )
        return list(result.scalars().all())

    async def upsert_device(self, user_id: int, payload: dict[str, Any]) -> PushSubscriptionModel:
        stmt = insert(PushSubscriptionModel).values(
            user_id=user_id,
            device_id=payload["device_id"],
            endpoint=payload["endpoint"],
            provider=payload["provider"],
            public_key=payload.get("public_key"),
            auth_key=payload.get("auth_key"),
            user_agent=payload.get("user_agent"),
            locale=payload.get("locale"),
            timezone=payload.get("timezone"),
            extra=payload.get("extra") or {},
            is_active=True,
            last_seen_at=utcnow(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[PushSubscriptionModel.user_id, PushSubscriptionModel.device_id],
            set_={
                "endpoint": payload["endpoint"],
                "provider": payload["provider"],
                "public_key": payload.get("public_key"),
                "auth_key": payload.get("auth_key"),
                "user_agent": payload.get("user_agent"),
                "locale": payload.get("locale"),
                "timezone": payload.get("timezone"),
                "extra": payload.get("extra") or {},
                "is_active": True,
                "last_seen_at": utcnow(),
            },
        )
        await self.session.execute(stmt)
        await self.session.flush()
        device = await self.get_device(user_id, str(payload["device_id"]))
        if device is None:
            raise RuntimeError("Failed to upsert push subscription")
        return device

    async def disable_device(self, user_id: int, device_id: str) -> PushSubscriptionModel | None:
        device = await self.get_device(user_id, device_id)
        if device is None or not device.is_active:
            return None
        device.is_active = False
        device.last_seen_at = utcnow()
        await self.session.flush()
        return device

    async def get_device(self, user_id: int, device_id: str) -> PushSubscriptionModel | None:
        result = await self.session.execute(
            select(PushSubscriptionModel).where(
                PushSubscriptionModel.user_id == user_id,
                PushSubscriptionModel.device_id == device_id,
            )
        )
        return result.scalar_one_or_none()


class ReceiptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _map_latest_receipts(
        rows: list[MessageReceiptModel | MessageReceiptArchiveModel],
    ) -> dict[str, MessageReceiptModel | MessageReceiptArchiveModel]:
        receipts: dict[str, MessageReceiptModel | MessageReceiptArchiveModel] = {}
        for receipt in rows:
            if receipt.notification_id not in receipts:
                receipts[receipt.notification_id] = receipt
        return receipts

    async def create_receipt(
        self,
        notification_id: str,
        user_id: int,
        ack_required: bool = False,
        ack_deadline_at: datetime | None = None,
    ) -> MessageReceiptModel:
        receipt = MessageReceiptModel(
            notification_id=notification_id,
            user_id=user_id,
            ack_required=ack_required,
            ack_deadline_at=ack_deadline_at,
        )
        self.session.add(receipt)
        await self.session.flush()
        return receipt

    async def get_by_id(self, receipt_id: str) -> MessageReceiptModel | None:
        result = await self.session.execute(
            select(MessageReceiptModel).where(MessageReceiptModel.id == receipt_id)
        )
        return result.scalar_one_or_none()

    async def get_latest_receipt(self, notification_id: str, user_id: int):
        active = await self.session.execute(
            select(MessageReceiptModel)
            .where(
                MessageReceiptModel.notification_id == notification_id,
                MessageReceiptModel.user_id == user_id,
            )
            .order_by(MessageReceiptModel.created_at.desc(), MessageReceiptModel.id.desc())
            .limit(1)
        )
        active_receipt = active.scalar_one_or_none()
        if active_receipt is not None:
            return active_receipt

        archived = await self.session.execute(
            select(MessageReceiptArchiveModel)
            .where(
                MessageReceiptArchiveModel.notification_id == notification_id,
                MessageReceiptArchiveModel.user_id == user_id,
            )
            .order_by(
                MessageReceiptArchiveModel.created_at.desc(), MessageReceiptArchiveModel.id.desc()
            )
            .limit(1)
        )
        return archived.scalar_one_or_none()

    async def list_latest_receipts(
        self,
        notification_ids: Iterable[str],
        user_id: int,
    ) -> dict[str, MessageReceiptModel | MessageReceiptArchiveModel]:
        normalized_ids = list(
            dict.fromkeys(str(notification_id) for notification_id in notification_ids)
        )
        if not normalized_ids:
            return {}

        active = await self.session.execute(
            select(MessageReceiptModel)
            .where(
                MessageReceiptModel.notification_id.in_(normalized_ids),
                MessageReceiptModel.user_id == user_id,
            )
            .order_by(
                MessageReceiptModel.notification_id.asc(),
                MessageReceiptModel.created_at.desc(),
                MessageReceiptModel.id.desc(),
            )
        )
        receipts = self._map_latest_receipts(list(active.scalars().all()))

        missing_ids = [
            notification_id for notification_id in normalized_ids if notification_id not in receipts
        ]
        if not missing_ids:
            return receipts

        archived = await self.session.execute(
            select(MessageReceiptArchiveModel)
            .where(
                MessageReceiptArchiveModel.notification_id.in_(missing_ids),
                MessageReceiptArchiveModel.user_id == user_id,
            )
            .order_by(
                MessageReceiptArchiveModel.notification_id.asc(),
                MessageReceiptArchiveModel.created_at.desc(),
                MessageReceiptArchiveModel.id.desc(),
            )
        )
        receipts.update(self._map_latest_receipts(list(archived.scalars().all())))
        return receipts

    async def mark_opened(self, notification_id: str, user_id: int) -> None:
        receipt = await self.get_latest_receipt(notification_id, user_id)
        if receipt is None:
            return
        if getattr(receipt, "opened_at", None) is None:
            receipt.opened_at = utcnow()
        if hasattr(receipt, "updated_at"):
            receipt.updated_at = utcnow()
        await self.session.flush()

    async def acknowledge(self, notification_id: str, user_id: int):
        receipt = await self.get_latest_receipt(notification_id, user_id)
        if receipt is None:
            return None

        if getattr(receipt, "opened_at", None) is None:
            receipt.opened_at = utcnow()
        if getattr(receipt, "acknowledged_at", None) is None:
            receipt.acknowledged_at = utcnow()
        if getattr(receipt, "manual_follow_up_status", None) not in (None, "none"):
            receipt.manual_follow_up_status = "resolved"
            receipt.manual_follow_up_updated_at = utcnow()
        if hasattr(receipt, "updated_at"):
            receipt.updated_at = utcnow()
        await self.session.flush()
        return receipt

    async def acknowledge_many(self, notification_ids: Iterable[str], user_id: int) -> None:
        normalized_ids = list(
            dict.fromkeys(str(notification_id) for notification_id in notification_ids)
        )
        if not normalized_ids:
            return

        receipts = await self.list_latest_receipts(normalized_ids, user_id)
        timestamp = utcnow()
        mutated = False
        for notification_id in normalized_ids:
            receipt = receipts.get(notification_id)
            if receipt is None:
                continue
            if getattr(receipt, "opened_at", None) is None:
                receipt.opened_at = timestamp
                mutated = True
            if getattr(receipt, "acknowledged_at", None) is None:
                receipt.acknowledged_at = timestamp
                mutated = True
            if getattr(receipt, "manual_follow_up_status", None) not in (None, "none"):
                receipt.manual_follow_up_status = "resolved"
                receipt.manual_follow_up_updated_at = timestamp
                mutated = True
            if hasattr(receipt, "updated_at"):
                receipt.updated_at = timestamp
                mutated = True
        if mutated:
            await self.session.flush()

    async def record_delivery(
        self,
        notification_id: str,
        user_id: int,
        channel: str,
        status: str,
    ) -> MessageReceiptModel | MessageReceiptArchiveModel | None:
        receipt = await self.get_latest_receipt(notification_id, user_id)
        if receipt is None:
            return None
        receipt.last_delivery_channel = channel
        receipt.last_delivery_status = status
        if hasattr(receipt, "updated_at"):
            receipt.updated_at = utcnow()
        await self.session.flush()
        return receipt

    async def mark_manual_follow_up_pending(
        self,
        receipt_id: str,
        escalation_level: int,
    ) -> MessageReceiptModel | None:
        receipt = await self.get_by_id(receipt_id)
        if receipt is None:
            return None
        receipt.manual_follow_up_status = "pending"
        receipt.manual_follow_up_updated_at = utcnow()
        receipt.escalation_level = max(int(receipt.escalation_level or 0), escalation_level)
        receipt.updated_at = utcnow()
        await self.session.flush()
        return receipt

    async def claim_manual_follow_up(self, receipt_id: str) -> MessageReceiptModel | None:
        receipt = await self.get_by_id(receipt_id)
        if receipt is None:
            return None
        receipt.manual_follow_up_status = "claimed"
        receipt.manual_follow_up_updated_at = utcnow()
        receipt.updated_at = utcnow()
        await self.session.flush()
        return receipt

    async def resolve_follow_up(self, receipt_id: str) -> MessageReceiptModel | None:
        receipt = await self.get_by_id(receipt_id)
        if receipt is None:
            return None
        receipt.manual_follow_up_status = "resolved"
        receipt.manual_follow_up_updated_at = utcnow()
        receipt.updated_at = utcnow()
        await self.session.flush()
        return receipt

    async def list_overdue_receipts(self, limit: int = 100) -> list[MessageReceiptModel]:
        result = await self.session.execute(
            select(MessageReceiptModel)
            .where(
                MessageReceiptModel.ack_required.is_(True),
                MessageReceiptModel.acknowledged_at.is_(None),
                MessageReceiptModel.ack_deadline_at.is_not(None),
                MessageReceiptModel.manual_follow_up_status.in_(["none", "pending"]),
                MessageReceiptModel.ack_deadline_at < utcnow(),
            )
            .order_by(MessageReceiptModel.ack_deadline_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    def _apply_admin_receipt_filters(
        self,
        stmt,
        *,
        follow_up_status: str | None = None,
        delivery_status: str | None = None,
        ack_required: bool | None = None,
        overdue_only: bool = False,
        user_id: int | None = None,
        notification_id: str | None = None,
    ):
        if follow_up_status is not None:
            stmt = stmt.where(MessageReceiptModel.manual_follow_up_status == follow_up_status)
        if delivery_status is not None:
            stmt = stmt.where(MessageReceiptModel.last_delivery_status == delivery_status)
        if ack_required is not None:
            stmt = stmt.where(MessageReceiptModel.ack_required.is_(ack_required))
        if user_id is not None:
            stmt = stmt.where(MessageReceiptModel.user_id == user_id)
        if notification_id is not None:
            stmt = stmt.where(MessageReceiptModel.notification_id == notification_id)
        if overdue_only:
            stmt = stmt.where(
                MessageReceiptModel.ack_required.is_(True),
                MessageReceiptModel.acknowledged_at.is_(None),
                MessageReceiptModel.ack_deadline_at.is_not(None),
                MessageReceiptModel.ack_deadline_at < utcnow(),
            )
        return stmt

    async def list_admin_receipts(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        follow_up_status: str | None = None,
        delivery_status: str | None = None,
        ack_required: bool | None = None,
        overdue_only: bool = False,
        user_id: int | None = None,
        notification_id: str | None = None,
    ) -> list[MessageReceiptModel]:
        stmt = self._apply_admin_receipt_filters(
            select(MessageReceiptModel),
            follow_up_status=follow_up_status,
            delivery_status=delivery_status,
            ack_required=ack_required,
            overdue_only=overdue_only,
            user_id=user_id,
            notification_id=notification_id,
        )
        stmt = (
            stmt.order_by(
                MessageReceiptModel.updated_at.desc(),
                MessageReceiptModel.created_at.desc(),
                MessageReceiptModel.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_admin_receipts(
        self,
        *,
        follow_up_status: str | None = None,
        delivery_status: str | None = None,
        ack_required: bool | None = None,
        overdue_only: bool = False,
        user_id: int | None = None,
        notification_id: str | None = None,
    ) -> int:
        stmt = self._apply_admin_receipt_filters(
            select(func.count(MessageReceiptModel.id)),
            follow_up_status=follow_up_status,
            delivery_status=delivery_status,
            ack_required=ack_required,
            overdue_only=overdue_only,
            user_id=user_id,
            notification_id=notification_id,
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def archive_terminal_receipts(
        self,
        *,
        retention_days: int,
        limit: int = 1000,
        delivery_statuses: Iterable[str] | None = None,
    ) -> int:
        if retention_days <= 0 or limit <= 0:
            return 0

        terminal_statuses = tuple(
            dict.fromkeys(
                str(status).strip().lower()
                for status in (delivery_statuses or ("delivered", "failed"))
                if str(status).strip()
            )
        )
        if not terminal_statuses:
            return 0

        cutoff = utcnow() - timedelta(days=retention_days)
        terminal_at = func.coalesce(
            MessageReceiptModel.acknowledged_at,
            MessageReceiptModel.opened_at,
            MessageReceiptModel.created_at,
        )
        result = await self.session.execute(
            select(MessageReceiptModel)
            .where(
                MessageReceiptModel.last_delivery_status.in_(terminal_statuses),
                or_(
                    MessageReceiptModel.ack_required.is_(False),
                    MessageReceiptModel.acknowledged_at.is_not(None),
                ),
                MessageReceiptModel.manual_follow_up_status.in_(["none", "resolved"]),
                terminal_at < cutoff,
            )
            .order_by(terminal_at.asc(), MessageReceiptModel.id.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        receipts = list(result.scalars().all())
        if not receipts:
            return 0

        self.session.add_all(
            [
                MessageReceiptArchiveModel(
                    id=receipt.id,
                    notification_id=receipt.notification_id,
                    user_id=receipt.user_id,
                    ack_required=receipt.ack_required,
                    ack_deadline_at=receipt.ack_deadline_at,
                    opened_at=receipt.opened_at,
                    acknowledged_at=receipt.acknowledged_at,
                    last_delivery_channel=receipt.last_delivery_channel,
                    last_delivery_status=receipt.last_delivery_status,
                    escalation_level=receipt.escalation_level,
                    manual_follow_up_status=receipt.manual_follow_up_status,
                    manual_follow_up_updated_at=receipt.manual_follow_up_updated_at,
                    created_at=receipt.created_at,
                    updated_at=receipt.updated_at,
                )
                for receipt in receipts
            ]
        )
        await self.session.execute(
            delete(MessageReceiptModel).where(
                MessageReceiptModel.id.in_([receipt.id for receipt in receipts])
            )
        )
        await self.session.flush()
        return len(receipts)


class MessageOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _with_claim_metadata(
        payload: dict[str, Any] | None, *, claimed_at: datetime
    ) -> dict[str, Any]:
        updated = dict(payload or {})
        updated["_claimed_at"] = claimed_at.isoformat()
        return updated

    @staticmethod
    def _clear_claim_metadata(payload: dict[str, Any] | None) -> dict[str, Any]:
        updated = dict(payload or {})
        updated.pop("_claimed_at", None)
        return updated

    @staticmethod
    def _get_claimed_at(message: MessageOutboxModel) -> datetime:
        payload = dict(message.payload or {})
        raw_claimed_at = payload.get("_claimed_at")
        if isinstance(raw_claimed_at, str) and raw_claimed_at:
            try:
                return datetime.fromisoformat(raw_claimed_at.replace("Z", "+00:00"))
            except ValueError:
                pass
        return message.created_at

    async def create(
        self,
        notification_id: str | None,
        user_id: int,
        channel: str,
        payload: dict[str, Any],
    ) -> MessageOutboxModel:
        message = MessageOutboxModel(
            notification_id=notification_id,
            user_id=user_id,
            channel=channel,
            payload=payload,
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def bulk_create(self, rows: list[dict[str, Any]]) -> list[MessageOutboxModel]:
        items = [MessageOutboxModel(**row) for row in rows]
        self.session.add_all(items)
        await self.session.flush()
        return items

    async def list_pending(self, channel: str, limit: int = 100) -> list[MessageOutboxModel]:
        result = await self.session.execute(
            select(MessageOutboxModel)
            .where(
                MessageOutboxModel.channel == channel,
                MessageOutboxModel.status == "pending",
            )
            .order_by(MessageOutboxModel.created_at.asc(), MessageOutboxModel.id.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    def _apply_admin_outbox_filters(
        self,
        stmt,
        *,
        channel: str | None = None,
        status: str | None = None,
        user_id: int | None = None,
        notification_id: str | None = None,
    ):
        if channel is not None:
            stmt = stmt.where(MessageOutboxModel.channel == channel)
        if status is not None:
            stmt = stmt.where(MessageOutboxModel.status == status)
        if user_id is not None:
            stmt = stmt.where(MessageOutboxModel.user_id == user_id)
        if notification_id is not None:
            stmt = stmt.where(MessageOutboxModel.notification_id == notification_id)
        return stmt

    async def list_admin_messages(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        channel: str | None = None,
        status: str | None = None,
        user_id: int | None = None,
        notification_id: str | None = None,
    ) -> list[MessageOutboxModel]:
        stmt = self._apply_admin_outbox_filters(
            select(MessageOutboxModel),
            channel=channel,
            status=status,
            user_id=user_id,
            notification_id=notification_id,
        )
        stmt = (
            stmt.order_by(
                MessageOutboxModel.created_at.desc(),
                MessageOutboxModel.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_admin_messages(
        self,
        *,
        channel: str | None = None,
        status: str | None = None,
        user_id: int | None = None,
        notification_id: str | None = None,
    ) -> int:
        stmt = self._apply_admin_outbox_filters(
            select(func.count(MessageOutboxModel.id)),
            channel=channel,
            status=status,
            user_id=user_id,
            notification_id=notification_id,
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def claim_pending(self, channel: str, limit: int = 100) -> list[MessageOutboxModel]:
        result = await self.session.execute(
            select(MessageOutboxModel)
            .where(
                MessageOutboxModel.channel == channel,
                MessageOutboxModel.status == "pending",
            )
            .order_by(MessageOutboxModel.created_at.asc(), MessageOutboxModel.id.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        messages = list(result.scalars().all())
        claimed_at = utcnow()
        for message in messages:
            message.status = "processing"
            message.payload = self._with_claim_metadata(message.payload, claimed_at=claimed_at)
        await self.session.flush()
        return messages

    async def get_by_id(self, outbox_id: str) -> MessageOutboxModel | None:
        result = await self.session.execute(
            select(MessageOutboxModel).where(MessageOutboxModel.id == outbox_id)
        )
        return result.scalar_one_or_none()

    async def mark_processing(self, outbox_id: str) -> MessageOutboxModel | None:
        message = await self.get_by_id(outbox_id)
        if message is None:
            return None
        message.status = "processing"
        message.payload = self._with_claim_metadata(message.payload, claimed_at=utcnow())
        await self.session.flush()
        return message

    async def mark_delivered(self, outbox_id: str) -> MessageOutboxModel | None:
        message = await self.get_by_id(outbox_id)
        if message is None:
            return None
        message.status = "delivered"
        message.payload = self._clear_claim_metadata(message.payload)
        await self.session.flush()
        return message

    async def mark_failed(
        self,
        outbox_id: str,
        error_message: str | None = None,
    ) -> MessageOutboxModel | None:
        message = await self.get_by_id(outbox_id)
        if message is None:
            return None
        payload = self._clear_claim_metadata(message.payload)
        if error_message:
            payload["_last_error"] = error_message
        message.payload = payload
        message.status = "failed"
        await self.session.flush()
        return message

    async def requeue(self, outbox_id: str) -> MessageOutboxModel | None:
        message = await self.get_by_id(outbox_id)
        if message is None:
            return None
        payload = self._clear_claim_metadata(message.payload)
        payload.pop("_last_error", None)
        message.payload = payload
        message.status = "pending"
        await self.session.flush()
        return message

    async def release_stale_processing(
        self,
        *,
        channel: str | None = None,
        older_than_minutes: int = 15,
        limit: int = 100,
    ) -> list[MessageOutboxModel]:
        stmt = select(MessageOutboxModel).where(MessageOutboxModel.status == "processing")
        if channel is not None:
            stmt = stmt.where(MessageOutboxModel.channel == channel)

        result = await self.session.execute(
            stmt.order_by(MessageOutboxModel.created_at.asc(), MessageOutboxModel.id.asc())
        )
        cutoff = utcnow() - timedelta(minutes=older_than_minutes)
        stale_messages: list[MessageOutboxModel] = []
        for message in result.scalars().all():
            claimed_at = self._get_claimed_at(message)
            if claimed_at >= cutoff:
                continue
            payload = self._clear_claim_metadata(message.payload)
            message.payload = payload
            message.status = "pending"
            stale_messages.append(message)
            if len(stale_messages) >= limit:
                break

        if stale_messages:
            await self.session.flush()
        return stale_messages

    async def delete_terminal_messages(
        self,
        *,
        retention_days: int,
        limit: int = 1000,
        statuses: Iterable[str] | None = None,
    ) -> int:
        if retention_days <= 0 or limit <= 0:
            return 0

        terminal_statuses = tuple(
            dict.fromkeys(
                str(status).strip().lower()
                for status in (statuses or ("delivered", "failed"))
                if str(status).strip()
            )
        )
        if not terminal_statuses:
            return 0

        cutoff = utcnow() - timedelta(days=retention_days)
        result = await self.session.execute(
            select(MessageOutboxModel.id)
            .where(
                MessageOutboxModel.status.in_(terminal_statuses),
                MessageOutboxModel.created_at < cutoff,
            )
            .order_by(MessageOutboxModel.created_at.asc(), MessageOutboxModel.id.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        outbox_ids = [str(outbox_id) for outbox_id in result.scalars().all()]
        if not outbox_ids:
            return 0

        await self.session.execute(
            delete(MessageOutboxModel).where(MessageOutboxModel.id.in_(outbox_ids))
        )
        await self.session.flush()
        return len(outbox_ids)


class DeliveryAttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_attempt(
        self,
        channel: str,
        status: str,
        receipt_id: str | None = None,
        notification_id: str | None = None,
        error_message: str | None = None,
    ) -> DeliveryAttemptModel:
        attempt = DeliveryAttemptModel(
            receipt_id=receipt_id,
            notification_id=notification_id,
            channel=channel,
            status=status,
            error_message=error_message,
        )
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def mark_success(self, attempt: DeliveryAttemptModel) -> DeliveryAttemptModel:
        attempt.status = "success"
        attempt.error_message = None
        await self.session.flush()
        return attempt

    async def mark_failure(
        self, attempt: DeliveryAttemptModel, error_message: str
    ) -> DeliveryAttemptModel:
        attempt.status = "failed"
        attempt.error_message = error_message
        await self.session.flush()
        return attempt
