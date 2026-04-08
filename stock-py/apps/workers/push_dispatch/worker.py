from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from infra.security.webpush import load_vapid_private_key
from infra.observability.runtime_monitoring import run_runtime_monitored

logger = logging.getLogger(__name__)


class PushDispatchWorker:
    def __init__(self, batch_size: int = 100) -> None:
        self.batch_size = batch_size

    async def process_event(self, topic: str, payload: dict[str, Any]) -> dict[str, Any]:
        if topic != "notification.requested":
            raise ValueError(f"Unsupported push dispatch topic: {topic}")
        if str(payload.get("channel") or "").lower() != "push":
            return {"processed": False, "delivered": False, "invalidated": 0}
        outbox_id = payload.get("outbox_id")
        if outbox_id in (None, ""):
            return {"processed": False, "delivered": False, "invalidated": 0}
        return await self.process_outbox_message(str(outbox_id))

    async def run_once(self) -> dict[str, int]:
        pending_ids = await self._claim_pending_ids()
        stats = {"processed": 0, "delivered": 0, "failed": 0, "invalidated": 0}

        for outbox_id in pending_ids:
            result = await self.process_outbox_message(outbox_id)
            if not result["processed"]:
                continue
            stats["processed"] += 1
            stats["invalidated"] += result["invalidated"]
            if result["delivered"]:
                stats["delivered"] += 1
            else:
                stats["failed"] += 1

        return stats

    async def process_outbox_message(self, outbox_id: str) -> dict[str, Any]:
        from domains.notifications.repository import (
            DeliveryAttemptRepository,
            MessageOutboxRepository,
            PushSubscriptionRepository,
            ReceiptRepository,
        )
        from infra.db.session import get_session_factory
        from infra.events.outbox import OutboxPublisher

        session_factory = get_session_factory()

        async with session_factory() as session:
            outbox_repository = MessageOutboxRepository(session)
            push_subscription_repository = PushSubscriptionRepository(session)
            receipt_repository = ReceiptRepository(session)
            delivery_attempt_repository = DeliveryAttemptRepository(session)
            publisher = OutboxPublisher(session)

            message = await outbox_repository.get_by_id(outbox_id)
            if message is None or message.channel != "push":
                return {"processed": False, "delivered": False, "invalidated": 0}

            if message.status not in {"pending", "processing"}:
                return {"processed": False, "delivered": False, "invalidated": 0}

            if message.status == "pending":
                await outbox_repository.mark_processing(outbox_id)

            receipt = None
            if message.notification_id:
                receipt = await receipt_repository.get_latest_receipt(
                    message.notification_id,
                    message.user_id,
                )

            attempt = await delivery_attempt_repository.record_attempt(
                channel="push",
                status="pending",
                receipt_id=getattr(receipt, "id", None),
                notification_id=message.notification_id,
            )

            devices = await push_subscription_repository.list_active_devices(message.user_id)
            if not devices:
                error_message = "no_active_push_devices"
                await delivery_attempt_repository.mark_failure(attempt, error_message)
                await outbox_repository.mark_failed(outbox_id, error_message)
                if message.notification_id:
                    await receipt_repository.record_delivery(
                        message.notification_id,
                        message.user_id,
                        "push",
                        "failed",
                    )
                await session.commit()
                return {"processed": True, "delivered": False, "invalidated": 0}

            delivered = False
            invalidated = 0
            last_error = "push_delivery_failed"
            payload = dict(message.payload or {})

            for device in devices:
                success, was_invalidated, error_message = await self._send_to_device(
                    device, payload
                )
                if was_invalidated:
                    invalidated += 1
                    await push_subscription_repository.disable_device(
                        message.user_id, device.device_id
                    )
                if success:
                    delivered = True
                    last_error = ""
                    break
                if error_message:
                    last_error = error_message

            if delivered:
                await delivery_attempt_repository.mark_success(attempt)
                await outbox_repository.mark_delivered(outbox_id)
                if message.notification_id:
                    await receipt_repository.record_delivery(
                        message.notification_id,
                        message.user_id,
                        "push",
                        "delivered",
                    )
                await publisher.publish_after_commit(
                    topic="notification.delivered",
                    key=message.id,
                    payload={
                        "outbox_id": message.id,
                        "notification_id": message.notification_id,
                        "user_id": message.user_id,
                        "channel": "push",
                    },
                )
            else:
                await delivery_attempt_repository.mark_failure(attempt, last_error)
                await outbox_repository.mark_failed(outbox_id, last_error)
                if message.notification_id:
                    await receipt_repository.record_delivery(
                        message.notification_id,
                        message.user_id,
                        "push",
                        "failed",
                    )

            await session.commit()
            return {
                "processed": True,
                "delivered": delivered,
                "invalidated": invalidated,
            }

    async def _claim_pending_ids(self) -> list[str]:
        from domains.notifications.repository import MessageOutboxRepository
        from infra.db.session import get_session_factory

        session_factory = get_session_factory()
        async with session_factory() as session:
            repository = MessageOutboxRepository(session)
            messages = await repository.claim_pending("push", limit=self.batch_size)
            await session.commit()
            return [message.id for message in messages]

    async def _send_to_device(
        self, device: Any, payload: dict[str, Any]
    ) -> tuple[bool, bool, str | None]:
        if device.provider != "webpush":
            return False, False, "provider_not_implemented"

        from infra.core.config import get_settings

        settings = get_settings()
        if not settings.web_push_public_key or not settings.web_push_private_key:
            return False, False, "web_push_not_configured"

        try:
            from pywebpush import WebPushException, webpush
        except ImportError:
            return False, False, "pywebpush_not_installed"

        try:
            await asyncio.to_thread(
                webpush,
                subscription_info={
                    "endpoint": device.endpoint,
                    "keys": {
                        "p256dh": device.public_key or "",
                        "auth": device.auth_key or "",
                    },
                },
                data=json.dumps(
                    {
                        "title": payload.get("title", "Notification"),
                        "body": payload.get("body", ""),
                        "url": payload.get("url", "/app/notifications"),
                        "tag": payload.get("tag", f"notification-{device.device_id}"),
                        "metadata": payload.get("metadata") or {},
                    }
                ),
                vapid_private_key=load_vapid_private_key(settings.web_push_private_key),
                vapid_claims={"sub": settings.web_push_subject},
            )
        except WebPushException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code in (404, 410):
                return False, True, f"webpush_invalid_{status_code}"
            return False, False, str(exc)
        except Exception as exc:
            return False, False, str(exc)

        return True, False, None


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    result = await run_runtime_monitored(
        "push-dispatch",
        "worker",
        PushDispatchWorker().run_once,
        metadata={"mode": "batch"},
        final_status="completed",
    )
    logger.info("Push dispatch batch finished: %s", result)


if __name__ == "__main__":
    asyncio.run(main())
