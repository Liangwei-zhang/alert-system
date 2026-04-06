"""
Projection mapper for TradingAgents responses.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from domains.tradingagents.schemas import TradingAgentsJobTerminalEvent, TradingAgentsProjection


class TradingAgentsProjectionMapper:
    """Maps API responses to projection schemas."""

    @staticmethod
    def from_webhook_payload(payload: dict) -> TradingAgentsProjection:
        """
        Map a webhook payload to TradingAgentsProjection.

        Expected webhook payload:
        {
            "request_id": "TA-20240404-abc123",
            "job_id": "job-xyz",
            "status": "completed|failed|timeout",
            "final_action": "buy|sell|hold|no_action",
            "decision_summary": "...",
            "result_payload": {...},
            "timestamp": "2024-04-04T12:00:00Z"
        }
        """
        return TradingAgentsProjection(
            request_id=payload.get("request_id", ""),
            job_id=payload.get("job_id"),
            tradingagents_status=payload.get("status", "unknown"),
            final_action=payload.get("final_action"),
            decision_summary=payload.get("decision_summary"),
            result_payload=payload.get("result_payload"),
        )

    @staticmethod
    def from_poll_response(
        request_id: str,
        job_id: str,
        poll_data: Dict[str, Any],
    ) -> TradingAgentsProjection:
        """
        Map a polling response to TradingAgentsProjection.

        Expected poll response:
        {
            "status": "completed|running|failed",
            "final_action": "buy|sell|hold|no_action",
            "decision_summary": "...",
            "result": {...}
        }
        """
        status = poll_data.get("status", "unknown")

        # Map status to our status enum
        if status == "completed":
            final_status = "completed"
        elif status == "running":
            final_status = "running"
        elif status == "failed":
            final_status = "failed"
        elif status == "timeout":
            final_status = "timeout"
        else:
            final_status = "unknown"

        return TradingAgentsProjection(
            request_id=request_id,
            job_id=job_id,
            tradingagents_status=final_status,
            final_action=poll_data.get("final_action"),
            decision_summary=poll_data.get("decision_summary"),
            result_payload=poll_data.get("result"),
        )

    @staticmethod
    def from_status_check(
        request_id: str,
        job_id: str,
        status_data: Dict[str, Any],
    ) -> TradingAgentsProjection:
        """
        Map a status check response to TradingAgentsProjection.

        Expected status response:
        {
            "status": "pending|submitted|running|completed|failed|timeout",
            "progress": 0.75,
            ...
        }
        """
        status = status_data.get("status", "unknown")

        # Map to our status format
        status_mapping = {
            "pending": "pending",
            "submitted": "submitted",
            "running": "running",
            "completed": "completed",
            "failed": "failed",
            "timeout": "timeout",
        }

        mapped_status = status_mapping.get(status, status)

        return TradingAgentsProjection(
            request_id=request_id,
            job_id=job_id,
            tradingagents_status=mapped_status,
            final_action=None,
            decision_summary=None,
            result_payload=None,
        )

    @staticmethod
    def extract_final_action(result_payload: Optional[dict]) -> Optional[str]:
        """Extract final action from result payload."""
        if not result_payload:
            return None

        # Try common paths for final action
        if "final_action" in result_payload:
            return result_payload["final_action"]
        if "decision" in result_payload:
            decision = result_payload["decision"]
            if isinstance(decision, dict):
                return decision.get("action")
            return decision
        if "analysis" in result_payload:
            analysis = result_payload["analysis"]
            if isinstance(analysis, dict):
                return analysis.get("recommendation")

        return None
