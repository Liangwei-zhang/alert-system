"""
Webhook router for TradingAgents terminal events.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from domains.tradingagents.webhook_service import TradingAgentsWebhookService
from infra.db.session import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/internal/tradingagents", tags=["tradingagents"])


@router.post("/job-terminal")
async def receive_terminal_event(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Receive terminal event webhook from TradingAgents.

    This endpoint is called when a job completes, fails, or times out.
    """
    try:
        # Get raw body for signature verification
        body = await request.body()

        # Parse JSON
        import json

        payload = json.loads(body)

        # Verify webhook signature (if configured)
        signature = request.headers.get("X-Webhook-Signature", "")
        secret = getattr(request.app.state, "webhook_secret", "")

        if secret and signature:
            webhook_service = TradingAgentsWebhookService(db)
            is_valid = await webhook_service.verify_webhook_signature(body, signature, secret)
            if not is_valid:
                raise HTTPException(status_code=401, detail="Invalid signature")

        # Handle the terminal event
        webhook_service = TradingAgentsWebhookService(db)
        result = await webhook_service.handle_terminal_event(payload)

        return result

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/job-status")
async def receive_status_update(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Receive status update webhook from TradingAgents.

    This endpoint is called for intermediate status updates.
    """
    try:
        body = await request.body()
        import json

        payload = json.loads(body)

        webhook_service = TradingAgentsWebhookService(db)
        result = await webhook_service.handle_status_update(payload)

        return result

    except Exception as e:
        logger.error(f"Error processing status update: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def webhook_health() -> dict:
    """Health check for webhook endpoint."""
    return {"status": "healthy", "endpoint": "tradingagents-webhook"}
