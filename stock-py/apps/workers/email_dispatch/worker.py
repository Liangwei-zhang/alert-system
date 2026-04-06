from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any

from infra.observability.runtime_monitoring import run_runtime_monitored

logger = logging.getLogger(__name__)


class EmailDispatchWorker:
    def __init__(self, batch_size: int = 100) -> None:
        self.batch_size = batch_size

    async def process_event(self, topic: str, payload: dict[str, Any]) -> dict[str, bool]:
        if topic != "notification.requested":
            raise ValueError(f"Unsupported email dispatch topic: {topic}")
        if str(payload.get("channel") or "").lower() != "email":
            return {"processed": False, "delivered": False}
        outbox_id = payload.get("outbox_id")
        if outbox_id in (None, ""):
            return {"processed": False, "delivered": False}
        return await self.process_outbox_message(str(outbox_id))

    async def run_once(self) -> dict[str, int]:
        pending_ids = await self._claim_pending_ids()
        stats = {"processed": 0, "delivered": 0, "failed": 0}

        for outbox_id in pending_ids:
            result = await self.process_outbox_message(outbox_id)
            if not result["processed"]:
                continue
            stats["processed"] += 1
            if result["delivered"]:
                stats["delivered"] += 1
            else:
                stats["failed"] += 1

        return stats

    async def process_outbox_message(self, outbox_id: str) -> dict[str, bool]:
        from sqlalchemy import select

        from domains.notifications.repository import (
            DeliveryAttemptRepository,
            MessageOutboxRepository,
            ReceiptRepository,
        )
        from infra.db.models.auth import UserModel
        from infra.db.session import get_session_factory
        from infra.events.outbox import OutboxPublisher

        session_factory = get_session_factory()

        async with session_factory() as session:
            outbox_repository = MessageOutboxRepository(session)
            receipt_repository = ReceiptRepository(session)
            delivery_attempt_repository = DeliveryAttemptRepository(session)
            publisher = OutboxPublisher(session)

            message = await outbox_repository.get_by_id(outbox_id)
            if message is None or message.channel != "email":
                return {"processed": False, "delivered": False}

            if message.status not in {"pending", "processing"}:
                return {"processed": False, "delivered": False}

            if message.status == "pending":
                await outbox_repository.mark_processing(outbox_id)

            receipt = None
            if message.notification_id:
                receipt = await receipt_repository.get_latest_receipt(
                    message.notification_id,
                    message.user_id,
                )

            attempt = await delivery_attempt_repository.record_attempt(
                channel="email",
                status="pending",
                receipt_id=getattr(receipt, "id", None),
                notification_id=message.notification_id,
            )

            result = await session.execute(
                select(UserModel).where(
                    UserModel.id == message.user_id,
                    UserModel.is_active.is_(True),
                )
            )
            user = result.scalar_one_or_none()

            if user is None or not user.email:
                error_message = "user_email_not_found"
                await delivery_attempt_repository.mark_failure(attempt, error_message)
                await outbox_repository.mark_failed(outbox_id, error_message)
                if message.notification_id:
                    await receipt_repository.record_delivery(
                        message.notification_id,
                        message.user_id,
                        "email",
                        "failed",
                    )
                await session.commit()
                return {"processed": True, "delivered": False}

            payload = dict(message.payload or {})
            delivered, error_message = await self._deliver_email(
                recipient_email=user.email,
                recipient_name=user.name,
                payload=payload,
            )

            if delivered:
                await delivery_attempt_repository.mark_success(attempt)
                await outbox_repository.mark_delivered(outbox_id)
                if message.notification_id:
                    await receipt_repository.record_delivery(
                        message.notification_id,
                        message.user_id,
                        "email",
                        "delivered",
                    )
                await publisher.publish_after_commit(
                    topic="notification.delivered",
                    key=message.id,
                    payload={
                        "outbox_id": message.id,
                        "notification_id": message.notification_id,
                        "user_id": message.user_id,
                        "channel": "email",
                    },
                )
            else:
                await delivery_attempt_repository.mark_failure(
                    attempt,
                    error_message or "email_delivery_failed",
                )
                await outbox_repository.mark_failed(
                    outbox_id,
                    error_message or "email_delivery_failed",
                )
                if message.notification_id:
                    await receipt_repository.record_delivery(
                        message.notification_id,
                        message.user_id,
                        "email",
                        "failed",
                    )

            await session.commit()
            return {"processed": True, "delivered": delivered}

    async def _claim_pending_ids(self) -> list[str]:
        from domains.notifications.repository import MessageOutboxRepository
        from infra.db.session import get_session_factory

        session_factory = get_session_factory()
        async with session_factory() as session:
            repository = MessageOutboxRepository(session)
            messages = await repository.claim_pending("email", limit=self.batch_size)
            await session.commit()
            return [message.id for message in messages]

    async def _deliver_email(
        self,
        recipient_email: str,
        recipient_name: str | None,
        payload: dict[str, Any],
    ) -> tuple[bool, str | None]:
        from infra.core.config import get_settings

        settings = get_settings()
        subject = str(payload.get("subject") or payload.get("title") or "Notification")
        text_body = str(payload.get("text_body") or payload.get("body") or "")
        html_body = payload.get("html_body") or self._default_html_body(subject, text_body)

        if not settings.smtp_host:
            if settings.environment == "production":
                return False, "smtp_not_configured"
            logger.info(
                "Email dispatch fallback recipient=%s subject=%s body=%s",
                recipient_email,
                subject,
                text_body,
            )
            return True, None

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = formataddr((settings.email_from_name, settings.email_from_address))
        message["To"] = formataddr((recipient_name or recipient_email, recipient_email))
        message.set_content(text_body)
        message.add_alternative(str(html_body), subtype="html")

        def send_message() -> None:
            with smtplib.SMTP(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            ) as client:
                if settings.smtp_use_tls:
                    client.starttls()
                if settings.smtp_username:
                    client.login(settings.smtp_username, settings.smtp_password)
                client.send_message(message)

        try:
            await asyncio.to_thread(send_message)
        except Exception as exc:
            return False, str(exc)

        return True, None

    @staticmethod
    def _default_html_body(subject: str, text_body: str) -> str:
        return "<html><body>" f"<h2>{subject}</h2>" f"<p>{text_body}</p>" "</body></html>"


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    result = await run_runtime_monitored(
        "email-dispatch",
        "worker",
        EmailDispatchWorker().run_once,
        metadata={"mode": "batch"},
        final_status="completed",
    )
    logger.info("Email dispatch batch finished: %s", result)


if __name__ == "__main__":
    asyncio.run(main())
