"""
Internal router for TradingAgents submission.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from domains.tradingagents.gateway import (
    TradingAgentsApiError,
    TradingAgentsGateway,
    TradingAgentsRateLimitError,
    TradingAgentsServerError,
)
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


@router.get("/stock-result/{request_id}")
async def get_tradingagents_stock_result(
    request_id: str,
    include_full_result_payload: bool = Query(
        False,
        description="Whether to ask TradingAgents for full result payload",
    ),
) -> JSONResponse:
    """
    Proxy stock-result polling to TradingAgents by request_id.

    The response preserves TradingAgents async semantics:
    - 200: terminal success payload
    - 202: still queued/running
    - 404: request not found
    - 409: terminal failure payload
    """
    try:
        gateway = TradingAgentsGateway()
        result = await gateway.get_stock_result(
            request_id=request_id,
            include_full_result_payload=include_full_result_payload,
        )

        if result is None:
            raise HTTPException(status_code=404, detail="Stock result not found")

        status_code = int(result.get("http_status") or 200)
        if status_code not in {200, 202, 409}:
            status_code = 200

        return JSONResponse(status_code=status_code, content=result)

    except HTTPException:
        raise
    except TradingAgentsRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except TradingAgentsServerError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except TradingAgentsApiError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Error polling stock result for {request_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
