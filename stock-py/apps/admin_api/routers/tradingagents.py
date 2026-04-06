"""
Admin router for TradingAgents management.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.admin_api.dependencies import get_tradingagents_read_model_service
from domains.analytics.tradingagents_read_model_service import TradingAgentsReadModelService
from domains.tradingagents.repository import TradingAgentsRepository
from domains.tradingagents.schemas import (
    ReconcileDelayedResponse,
    TradingAgentsAnalysisListQuery,
    TradingAgentsAnalysisResponse,
)
from infra.db.session import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin/tradingagents", tags=["admin", "tradingagents"])


def _record_to_response(record) -> TradingAgentsAnalysisResponse:
    """Convert a database record to response schema."""
    import json

    selected_analysts = None
    if record.selected_analysts:
        try:
            selected_analysts = json.loads(record.selected_analysts)
        except:
            pass

    trigger_context = None
    if record.trigger_context:
        try:
            trigger_context = json.loads(record.trigger_context)
        except:
            pass

    return TradingAgentsAnalysisResponse(
        id=record.id,
        request_id=record.request_id,
        job_id=record.job_id,
        ticker=record.ticker,
        analysis_date=record.analysis_date,
        selected_analysts=selected_analysts,
        trigger_type=record.trigger_type,
        trigger_context=trigger_context,
        tradingagents_status=(
            record.tradingagents_status.value
            if hasattr(record.tradingagents_status, "value")
            else record.tradingagents_status
        ),
        final_action=(
            record.final_action.value
            if hasattr(record.final_action, "value")
            else record.final_action
        ),
        decision_summary=record.decision_summary,
        submitted_at=record.submitted_at,
        completed_at=record.completed_at,
        delayed_at=record.delayed_at,
        created_at=record.created_at,
        poll_count=record.poll_count,
        webhook_received=record.webhook_received,
    )


@router.get("/analyses", response_model=dict)
async def list_analyses(
    status: Optional[str] = Query(
        None,
        pattern="^(pending|submitted|running|completed|failed|timeout)$",
        description="Filter by status",
    ),
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    trigger_type: Optional[str] = Query(
        None,
        pattern="^(scanner|manual|position_review|scheduled)$",
        description="Filter by trigger type",
    ),
    from_date: Optional[datetime] = Query(None, description="From date filter"),
    to_date: Optional[datetime] = Query(None, description="To date filter"),
    limit: int = Query(50, ge=1, le=500, description="Results limit"),
    offset: int = Query(0, ge=0, description="Results offset"),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    List TradingAgents analysis records.

    Supports filtering by status, ticker, trigger type, and date range.
    Pagination via limit and offset.
    """
    try:
        repository = TradingAgentsRepository(db)

        # Get records
        records = await repository.list_analyses(
            status=status,
            ticker=ticker,
            trigger_type=trigger_type,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            offset=offset,
        )

        # Get total count
        total = await repository.count_analyses(status=status, ticker=ticker)

        # Convert to response
        analyses = [_record_to_response(r) for r in records]

        return {
            "data": analyses,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(records)) < total,
        }

    except Exception as e:
        logger.error(f"Error listing analyses: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyses/{request_id}", response_model=TradingAgentsAnalysisResponse)
async def get_analysis(
    request_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> TradingAgentsAnalysisResponse:
    """Get a single analysis by request ID."""
    try:
        repository = TradingAgentsRepository(db)
        record = await repository.get_by_request_id(request_id)

        if not record:
            raise HTTPException(status_code=404, detail="Analysis not found")

        return _record_to_response(record)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting analysis {request_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reconcile-delayed", response_model=ReconcileDelayedResponse)
async def reconcile_delayed(
    delayed_threshold_minutes: int = Query(
        30, ge=5, le=1440, description="Threshold in minutes to consider a job delayed"
    ),
    db: AsyncSession = Depends(get_db_session),
) -> ReconcileDelayedResponse:
    """
    Reconcile delayed jobs.

    Finds jobs that have been in submitted/running state for longer than
    the threshold and attempts to poll for their status.
    """
    try:
        repository = TradingAgentsRepository(db)

        # Get delayed records
        delayed_records = await repository.list_delayed(
            delayed_threshold_minutes=delayed_threshold_minutes
        )

        processed_count = 0
        reconciled_count = 0
        failed_count = 0

        from domains.tradingagents.gateway import TradingAgentsGateway

        gateway = TradingAgentsGateway()

        for record in delayed_records:
            if not record.job_id:
                continue

            processed_count += 1

            try:
                # Poll for status
                result = await gateway.get_stock_result(record.job_id)

                if result:
                    status = result.get("status")

                    if status == "completed":
                        # Mark as completed
                        final_action = result.get("final_action", "unknown")
                        await repository.mark_completed(
                            request_id=record.request_id,
                            final_action=final_action,
                            decision_summary=result.get("decision_summary"),
                            result_payload=result,
                        )
                        reconciled_count += 1

                    elif status == "failed":
                        await repository.mark_failed(
                            request_id=record.request_id,
                            error_message=result.get("error", "Job failed"),
                        )
                        reconciled_count += 1

                    else:
                        # Still running, mark as delayed
                        await repository.mark_delayed(record.request_id)
                else:
                    # No result, mark as delayed
                    await repository.mark_delayed(record.request_id)

            except Exception as e:
                logger.error(f"Error processing delayed job {record.request_id}: {e}")
                failed_count += 1

        return ReconcileDelayedResponse(
            processed_count=processed_count,
            reconciled_count=reconciled_count,
            failed_count=failed_count,
            message=f"Processed {processed_count} delayed jobs, reconciled {reconciled_count}, failed {failed_count}",
        )

    except Exception as e:
        logger.error(f"Error reconciling delayed jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=dict)
async def get_stats(
    service: TradingAgentsReadModelService = Depends(get_tradingagents_read_model_service),
) -> dict:
    """Get TradingAgents statistics."""
    try:
        metrics = await service.build_tradingagents_view(24)
        return {
            "total": metrics.requested_total,
            "by_status": metrics.by_status,
            "last_24h": metrics.requested_total,
            "completed_total": metrics.completed_total,
            "failed_total": metrics.failed_total,
            "open_total": metrics.open_total,
            "terminal_total": metrics.terminal_total,
            "success_rate": metrics.success_rate,
            "avg_latency_seconds": metrics.avg_latency_seconds,
            "by_final_action": metrics.by_final_action,
        }

    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
