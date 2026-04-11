"""
Webhook service for TradingAgents terminal events.
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from domains.tradingagents.projection_mapper import TradingAgentsProjectionMapper
from domains.tradingagents.repository import TradingAgentsRepository
from domains.tradingagents.schemas import TradingAgentsJobTerminalEvent
from infra.events.outbox import OutboxPublisher

logger = logging.getLogger(__name__)


class TradingAgentsWebhookService:
    """Service for handling TradingAgents webhook events."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = TradingAgentsRepository(session)
        self.mapper = TradingAgentsProjectionMapper()

    async def handle_terminal_event(
        self,
        payload: dict,
    ) -> dict:
        """
        Handle a terminal event webhook from TradingAgents.

        Terminal events include:
        - completed: Job finished successfully
        - failed: Job failed
        - timeout: Job timed out

        Args:
            payload: Webhook payload

        Returns:
            Response dict with status
        """
        try:
            # TradingAgents may send either direct projection payload or
            # an envelope payload: {"event": "job_terminal", "projection": {...}}.
            if isinstance(payload.get("projection"), dict):
                if payload.get("event") not in {None, "job_terminal"}:
                    raise ValueError(f"Unsupported TradingAgents event: {payload.get('event')}")
                event_payload = dict(payload["projection"])
                if payload.get("delivered_at") and "delivered_at" not in event_payload:
                    event_payload["delivered_at"] = payload.get("delivered_at")
            else:
                event_payload = payload

            # Parse and validate payload
            event = TradingAgentsJobTerminalEvent(**event_payload)

            logger.info(
                f"Received terminal event for request_id={event.request_id}, "
                f"job_id={event.job_id}, status={event.tradingagents_status or event.status}"
            )

            # Map to projection
            projection = self.mapper.from_webhook_payload(payload)

            # Update the record
            await self.repository.update_projection(
                request_id=projection.request_id,
                job_id=projection.job_id,
                tradingagents_status=projection.tradingagents_status,
                final_action=projection.final_action,
                decision_summary=projection.decision_summary,
                result_payload=projection.result_payload,
            )

            # Mark as completed/failed based on mapped internal status.
            if projection.tradingagents_status == "completed":
                await self.repository.mark_completed(
                    request_id=event.request_id,
                    final_action=projection.final_action or "unknown",
                    decision_summary=projection.decision_summary,
                    result_payload=projection.result_payload,
                )
                logger.info(f"Marked {event.request_id} as completed")

            elif projection.tradingagents_status in {"failed", "timeout"}:
                if projection.tradingagents_status == "timeout":
                    terminal_error_message = projection.decision_summary or "Job timed out"
                else:
                    terminal_error_message = projection.decision_summary or "Job failed"
                await self.repository.mark_failed(
                    request_id=event.request_id,
                    error_message=terminal_error_message,
                )
                logger.warning(
                    "Marked %s as %s",
                    event.request_id,
                    projection.tradingagents_status,
                )

            # Mark webhook received
            await self.repository.mark_webhook_received(event.request_id)
            record = await self.repository.get_by_request_id(event.request_id)
            status_for_event = str(
                event.tradingagents_status
                or event.status
                or projection.tradingagents_status
                or "unknown"
            ).lower()
            await OutboxPublisher(self.session).publish_after_commit(
                topic="tradingagents.terminal",
                key=event.request_id,
                payload={
                    "request_id": event.request_id,
                    "job_id": event.job_id,
                    "ticker": getattr(record, "ticker", None) or event_payload.get("ticker"),
                    "status": status_for_event,
                    "final_action": projection.final_action,
                    "decision_summary": projection.decision_summary,
                    "result_payload": projection.result_payload,
                    "submitted_at": getattr(record, "submitted_at", None),
                    "completed_at": getattr(record, "completed_at", None),
                },
            )

            return {
                "success": True,
                "request_id": event.request_id,
                "status": "processed",
            }

        except Exception as e:
            logger.error(f"Error handling terminal event: {e}", exc_info=True)
            raise

    async def handle_status_update(
        self,
        payload: dict,
    ) -> dict:
        """
        Handle a status update webhook (non-terminal).

        Args:
            payload: Webhook payload

        Returns:
            Response dict
        """
        try:
            request_id = payload.get("request_id")
            job_id = payload.get("job_id")
            status = payload.get("tradingagents_status") or payload.get("status")

            if not request_id or not job_id:
                raise ValueError("Missing request_id or job_id in payload")

            logger.info(f"Status update for {request_id}: {status}")

            mapped_status = self.mapper.to_internal_status(status)

            # Update status
            await self.repository.update_projection(
                request_id=request_id,
                job_id=job_id,
                tradingagents_status=mapped_status,
            )

            return {
                "success": True,
                "request_id": request_id,
                "status": "updated",
            }

        except Exception as e:
            logger.error(f"Error handling status update: {e}", exc_info=True)
            raise

    async def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        """
        Verify webhook signature.

        Args:
            payload: Raw payload bytes
            signature: Signature from header
            secret: Webhook secret

        Returns:
            True if signature is valid
        """
        import hashlib
        import hmac

        expected_signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        return hmac.compare_digest(signature, expected_signature)
