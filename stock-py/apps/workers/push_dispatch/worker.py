from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from infra.core.config import get_settings
from infra.security.webpush import load_vapid_private_key
from infra.observability.runtime_monitoring import run_runtime_monitored

logger = logging.getLogger(__name__)


class PushDispatchWorker:
    def __init__(self, batch_size: int | None = None, max_concurrency: int | None = None) -> None:
        settings = get_settings()
        self.batch_size = max(int(batch_size or settings.push_dispatch_batch_size), 1)
        self.max_concurrency = max(
            int(max_concurrency or settings.push_dispatch_max_concurrency),
            1,
        )

    async def process_event(self, topic: str, payload: dict[str, Any]) -> dict[str, Any]:
        if topic == "notification.push.batch.requested":
            if str(payload.get("channel") or "").lower() != "push":
                return {"processed": 0, "delivered": 0, "failed": 0, "invalidated": 0}
            outbox_ids = [
                str(outbox_id)
                for outbox_id in (payload.get("outbox_ids") or [])
                if outbox_id not in (None, "")
            ]
            if not outbox_ids:
                return {"processed": 0, "delivered": 0, "failed": 0, "invalidated": 0}
            return await self.process_outbox_batch(outbox_ids)

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
        return await self.process_outbox_batch(pending_ids)

    async def process_outbox_batch(self, outbox_ids: list[str]) -> dict[str, int]:
        stats = {"processed": 0, "delivered": 0, "failed": 0, "invalidated": 0}
        if not outbox_ids:
            return stats

        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def _process_one(outbox_id: str) -> dict[str, Any]:
            async with semaphore:
                return await self.process_outbox_message(outbox_id)

        results = await asyncio.gather(
            *(_process_one(outbox_id) for outbox_id in outbox_ids),
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, Exception):
                logger.exception("Push dispatch batch item failed", exc_info=result)
                stats["failed"] += 1
                continue

            if not result.get("processed"):
                continue

            stats["processed"] += 1
            stats["invalidated"] += int(result.get("invalidated", 0) or 0)
            if result.get("delivered"):
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
            payload = self._decorate_push_payload(
                dict(message.payload or {}),
                message.notification_id,
            )

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
                        "title": payload.get("title", "系统通知"),
                        "body": payload.get("body", ""),
                        "url": payload.get("url", "/app/notifications"),
                        "notification_id": payload.get("notification_id"),
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

    @staticmethod
    def _decorate_push_payload(
        payload: dict[str, Any],
        notification_id: str | None,
    ) -> dict[str, Any]:
        if not notification_id:
            return payload

        normalized = str(notification_id)
        updated = dict(payload)
        updated["notification_id"] = normalized
        updated["url"] = PushDispatchWorker._append_notification_id(
            str(updated.get("url") or "/app/notifications"),
            normalized,
        )
        return updated

    @staticmethod
    def _append_notification_id(raw_url: str, notification_id: str) -> str:
        parsed = urlparse(raw_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["notification_id"] = notification_id
        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                urlencode(query),
                parsed.fragment,
            )
        )


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
