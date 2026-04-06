"""
Internal router for TradingAgents submission.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from domains.tradingagents.orchestrator import TradingAgentsOrchestrator
from domains.tradingagents.schemas import SubmitTradingAgentsRequest, SubmitTradingAgentsResponse
from infra.db.session import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/internal/tradingagents", tags=["tradingagents"])


@router.post("/submit", response_model=SubmitTradingAgentsResponse)
async def submit_tradingagents_job(
    request: SubmitTradingAgentsRequest,
    db: AsyncSession = Depends(get_db_session),
) -> SubmitTradingAgentsResponse:
    """
    Submit a TradingAgents analysis job.

    This is an internal endpoint for submitting analysis requests.
    """
    try:
        orchestrator = TradingAgentsOrchestrator(session=db)
        result = await orchestrator.submit_direct(request)

        return result

    except Exception as e:
        logger.error(f"Error submitting job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def internal_health() -> dict:
    """Health check for internal TradingAgents endpoint."""
    return {"status": "healthy", "endpoint": "tradingagents-internal"}
