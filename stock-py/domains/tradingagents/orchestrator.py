"""
Orchestrator for TradingAgents domain.
"""

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from domains.tradingagents.gateway import (
    TradingAgentsApiError,
    TradingAgentsGateway,
    TradingAgentsRateLimitError,
)
from domains.tradingagents.projection_mapper import TradingAgentsProjectionMapper
from domains.tradingagents.repository import TradingAgentsRepository
from domains.tradingagents.request_id import RequestIdBuilder
from domains.tradingagents.schemas import (
    SubmitTradingAgentsRequest,
    SubmitTradingAgentsResponse,
    TradingAgentsProjection,
)
from infra.core.config import get_settings
from infra.events.outbox import OutboxPublisher

logger = logging.getLogger(__name__)


class TradingAgentsOrchestrator:
    """Orchestrator for TradingAgents operations."""

    def __init__(
        self,
        session: AsyncSession,
        gateway: Optional[TradingAgentsGateway] = None,
    ):
        self.session = session
        self.repository = TradingAgentsRepository(session)
        self.gateway = gateway or TradingAgentsGateway()
        self.mapper = TradingAgentsProjectionMapper()

    async def submit_from_scanner(
        self,
        ticker: str,
        analysis_date: datetime,
        trigger_context: Optional[dict] = None,
    ) -> SubmitTradingAgentsResponse:
        """
        Submit a TradingAgents analysis triggered from scanner.

        Args:
            ticker: Stock ticker symbol
            analysis_date: Date to analyze
            trigger_context: Additional context from scanner (signal details, etc.)

        Returns:
            SubmitTradingAgentsResponse with request_id and status
        """
        request_id = RequestIdBuilder.build(
            ticker=ticker,
            analysis_date=analysis_date,
            trigger_type="scanner",
            trigger_context=trigger_context,
        )

        return await self._submit(
            request_id=request_id,
            ticker=ticker,
            analysis_date=analysis_date,
            trigger_type="scanner",
            trigger_context=trigger_context,
            selected_analysts=None,
        )

    async def submit_manual(
        self,
        ticker: str,
        analysis_date: datetime,
        selected_analysts: Optional[List[str]] = None,
        trigger_context: Optional[dict] = None,
    ) -> SubmitTradingAgentsResponse:
        """
        Submit a manual TradingAgents analysis request.

        Args:
            ticker: Stock ticker symbol
            analysis_date: Date to analyze
            selected_analysts: Optional list of specific analysts to use
            trigger_context: Additional context

        Returns:
            SubmitTradingAgentsResponse with request_id and status
        """
        request_id = RequestIdBuilder.build_from_components(
            ticker=ticker,
            analysis_date=analysis_date,
            selected_analysts=selected_analysts,
            trigger_type="manual",
            trigger_context=trigger_context,
        )

        return await self._submit(
            request_id=request_id,
            ticker=ticker,
            analysis_date=analysis_date,
            trigger_type="manual",
            trigger_context=trigger_context,
            selected_analysts=selected_analysts,
        )

    async def submit_position_review(
        self,
        ticker: str,
        analysis_date: datetime,
        position_context: dict,
    ) -> SubmitTradingAgentsResponse:
        """
        Submit a TradingAgents analysis for position review.

        Args:
            ticker: Stock ticker symbol
            analysis_date: Date to analyze
            position_context: Position details (entry price, current P/L, etc.)

        Returns:
            SubmitTradingAgentsResponse with request_id and status
        """
        trigger_context = {
            "type": "position_review",
            "position": position_context,
        }

        request_id = RequestIdBuilder.build(
            ticker=ticker,
            analysis_date=analysis_date,
            trigger_type="position_review",
            trigger_context=trigger_context,
        )

        return await self._submit(
            request_id=request_id,
            ticker=ticker,
            analysis_date=analysis_date,
            trigger_type="position_review",
            trigger_context=trigger_context,
            selected_analysts=None,
        )

    async def _submit(
        self,
        request_id: str,
        ticker: str,
        analysis_date: datetime,
        trigger_type: str,
        trigger_context: Optional[dict],
        selected_analysts: Optional[List[str]],
    ) -> SubmitTradingAgentsResponse:
        """Internal method to submit a request."""
        # First insert the record
        await self.repository.insert_accepted(
            request_id=request_id,
            ticker=ticker,
            analysis_date=analysis_date,
            trigger_type=trigger_type,
            selected_analysts=selected_analysts,
            trigger_context=trigger_context,
        )
        await self._publish_requested_event(
            request_id=request_id,
            ticker=ticker,
            analysis_date=analysis_date,
            trigger_type=trigger_type,
            selected_analysts=selected_analysts,
            trigger_context=trigger_context,
            status="accepted",
            job_id=None,
        )

        # Build the request
        request = SubmitTradingAgentsRequest(
            request_id=request_id,
            ticker=ticker,
            analysis_date=analysis_date,
            selected_analysts=selected_analysts,
            trigger_type=trigger_type,
            trigger_context=trigger_context,
        )

        try:
            # Submit to gateway
            result = await self.gateway.submit_job(request)

            # Update record with job_id
            job_id = result.get("job_id")
            if job_id:
                await self.repository.mark_submitted(request_id, job_id)

            return SubmitTradingAgentsResponse(
                request_id=request_id,
                job_id=job_id,
                status="submitted",
                message="Job submitted successfully",
            )

        except TradingAgentsRateLimitError as e:
            logger.warning(f"Rate limited submitting {request_id}: {e}")
            # Keep as pending, will be retried by worker
            return SubmitTradingAgentsResponse(
                request_id=request_id,
                job_id=None,
                status="pending",
                message="Rate limited, job queued for retry",
            )

        except TradingAgentsApiError as e:
            logger.error(f"API error submitting {request_id}: {e}")
            # Record the failure
            from domains.tradingagents.repository import TradingAgentsFailureRepository

            failure_repo = TradingAgentsFailureRepository(self.session)
            await failure_repo.record_submit_failure(
                request_id=request_id,
                ticker=ticker,
                error_message=str(e),
            )
            return SubmitTradingAgentsResponse(
                request_id=request_id,
                job_id=None,
                status="failed",
                message=f"Failed to submit: {str(e)}",
            )

    async def submit_direct(
        self,
        request: SubmitTradingAgentsRequest,
    ) -> SubmitTradingAgentsResponse:
        """
        Submit a request directly (from API endpoint).

        Args:
            request: Complete SubmitTradingAgentsRequest

        Returns:
            SubmitTradingAgentsResponse
        """
        existing, created = await self.repository.insert_accepted_if_absent(
            request_id=request.request_id,
            ticker=request.ticker,
            analysis_date=request.analysis_date,
            trigger_type=request.trigger_type,
            selected_analysts=request.selected_analysts,
            trigger_context=request.trigger_context,
        )
        if not created:
            return SubmitTradingAgentsResponse(
                request_id=request.request_id,
                job_id=getattr(existing, "job_id", None),
                status=getattr(getattr(existing, "tradingagents_status", None), "value", "pending"),
                message="Request already exists",
            )
        await self._publish_requested_event(
            request_id=request.request_id,
            ticker=request.ticker,
            analysis_date=request.analysis_date,
            trigger_type=request.trigger_type,
            selected_analysts=request.selected_analysts,
            trigger_context=request.trigger_context,
            status="accepted",
            job_id=None,
        )

        # Submit to gateway
        try:
            result = await self.gateway.submit_job(request)
            job_id = result.get("job_id")

            if job_id:
                await self.repository.mark_submitted(request.request_id, job_id)

            return SubmitTradingAgentsResponse(
                request_id=request.request_id,
                job_id=job_id,
                status="submitted",
                message="Job submitted successfully",
            )

        except TradingAgentsRateLimitError:
            return SubmitTradingAgentsResponse(
                request_id=request.request_id,
                job_id=None,
                status="pending",
                message="Rate limited, job queued for retry",
            )

        except TradingAgentsApiError as e:
            return SubmitTradingAgentsResponse(
                request_id=request.request_id,
                job_id=None,
                status="failed",
                message=f"Failed to submit: {str(e)}",
            )

    async def _publish_requested_event(
        self,
        *,
        request_id: str,
        ticker: str,
        analysis_date: datetime,
        trigger_type: str,
        selected_analysts: Optional[List[str]],
        trigger_context: Optional[dict],
        status: str,
        job_id: Optional[str],
    ) -> None:
        await OutboxPublisher(self.session).publish_after_commit(
            topic="tradingagents.requested",
            key=request_id,
            payload={
                "request_id": request_id,
                "job_id": job_id,
                "ticker": ticker,
                "analysis_date": analysis_date.isoformat(),
                "trigger_type": trigger_type,
                "selected_analysts": selected_analysts or [],
                "trigger_context": trigger_context or {},
                "status": status,
                "requested_at": datetime.utcnow().isoformat(),
            },
        )

    async def handle_webhook(
        self,
        payload: dict,
    ) -> bool:
        """
        Handle a webhook event.

        Args:
            payload: Webhook payload from TradingAgents

        Returns:
            True if handled successfully
        """
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

        if projection.tradingagents_status in ["completed", "failed", "timeout"]:
            await self.repository.mark_webhook_received(projection.request_id)

        return True

    async def poll_and_update(
        self,
        request_id: str,
    ) -> Optional[TradingAgentsProjection]:
        """
        Poll gateway for job status and update record.

        Args:
            request_id: Request ID to poll

        Returns:
            Updated projection or None if still running
        """
        record = await self.repository.get_by_request_id(request_id)
        if not record or not record.job_id:
            return None

        # Increment poll count
        await self.repository.increment_poll_count(request_id)

        try:
            poll_result = await self.gateway.get_stock_result(
                request_id=request_id,
                include_full_result_payload=get_settings().tradingagents_poll_include_full_result_payload,
            )

            if not poll_result:
                return None  # Job not found or still processing

            # Map to projection
            projection = self.mapper.from_poll_response(
                request_id=request_id,
                job_id=record.job_id,
                poll_data=poll_result,
            )

            # Update record
            await self.repository.update_projection(
                request_id=request_id,
                job_id=record.job_id,
                tradingagents_status=projection.tradingagents_status,
                final_action=projection.final_action,
                decision_summary=projection.decision_summary,
                result_payload=projection.result_payload,
            )

            # If completed, mark as such
            if projection.tradingagents_status == "completed":
                await self.repository.mark_completed(
                    request_id=request_id,
                    final_action=projection.final_action or "unknown",
                    decision_summary=projection.decision_summary,
                    result_payload=projection.result_payload,
                )
            elif projection.tradingagents_status in {"failed", "timeout"}:
                await self.repository.mark_failed(
                    request_id=request_id,
                    error_message=projection.decision_summary
                    or poll_result.get("error_message")
                    or "TradingAgents terminal failure",
                )

            return projection

        except TradingAgentsApiError as e:
            logger.error(f"Error polling {request_id}: {e}")
            return None
