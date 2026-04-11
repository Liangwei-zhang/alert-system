"""
Projection mapper for TradingAgents responses.
"""

from typing import Any, Dict, Optional

from domains.tradingagents.schemas import TradingAgentsProjection


class TradingAgentsProjectionMapper:
    """Maps API responses to projection schemas."""

    _STATUS_MAPPING = {
        "queued": "pending",
        "pending": "pending",
        "submitted": "submitted",
        "running": "running",
        "succeeded": "completed",
        "completed": "completed",
        "failed": "failed",
        "error": "failed",
        "canceled": "failed",
        "cancelled": "failed",
        "timeout": "timeout",
    }

    _FINAL_ACTION_MAPPING = {
        "buy": "buy",
        "sell": "sell",
        "hold": "hold",
        "no_action": "no_action",
        "add": "add",
        "reduce": "reduce",
    }

    @classmethod
    def to_internal_status(
        cls,
        status: Any,
        *,
        http_status: int | None = None,
    ) -> str:
        normalized = str(status or "").strip().lower()
        if normalized:
            return cls._STATUS_MAPPING.get(normalized, "running")
        if http_status == 200:
            return "completed"
        if http_status == 409:
            return "failed"
        if http_status == 202:
            return "running"
        return "running"

    @classmethod
    def normalize_final_action(cls, action: Any) -> Optional[str]:
        if action in (None, ""):
            return None
        normalized = str(action).strip().lower().replace(" ", "_")
        return cls._FINAL_ACTION_MAPPING.get(normalized, normalized)

    @staticmethod
    def _extract_projection_payload(payload: dict) -> dict:
        if isinstance(payload.get("projection"), dict):
            return payload["projection"]
        return payload

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
        projection_payload = TradingAgentsProjectionMapper._extract_projection_payload(payload)
        status = projection_payload.get("tradingagents_status") or projection_payload.get("status")
        result_payload = projection_payload.get("result_payload")
        if result_payload is None and isinstance(payload.get("result_payload"), dict):
            result_payload = payload.get("result_payload")

        final_action = (
            projection_payload.get("final_action")
            or payload.get("final_action")
            or TradingAgentsProjectionMapper.extract_final_action(result_payload)
        )
        decision_summary = (
            projection_payload.get("decision_summary")
            or projection_payload.get("error_message")
            or payload.get("decision_summary")
            or payload.get("error_message")
        )

        return TradingAgentsProjection(
            request_id=str(projection_payload.get("request_id") or payload.get("request_id") or ""),
            job_id=projection_payload.get("job_id") or payload.get("job_id"),
            tradingagents_status=TradingAgentsProjectionMapper.to_internal_status(
                status,
                http_status=payload.get("http_status"),
            ),
            final_action=TradingAgentsProjectionMapper.normalize_final_action(final_action),
            decision_summary=decision_summary,
            result_payload=result_payload,
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
        status = poll_data.get("tradingagents_status") or poll_data.get("status")
        result_payload = poll_data.get("result_payload")
        if result_payload is None:
            result_payload = poll_data.get("result")

        final_action = (
            poll_data.get("final_action")
            or TradingAgentsProjectionMapper.extract_final_action(result_payload)
        )
        decision_summary = poll_data.get("decision_summary") or poll_data.get("error_message")

        return TradingAgentsProjection(
            request_id=request_id,
            job_id=str(poll_data.get("job_id") or job_id),
            tradingagents_status=TradingAgentsProjectionMapper.to_internal_status(
                status,
                http_status=poll_data.get("http_status"),
            ),
            final_action=TradingAgentsProjectionMapper.normalize_final_action(final_action),
            decision_summary=decision_summary,
            result_payload=result_payload,
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
        status = status_data.get("tradingagents_status") or status_data.get("status")

        return TradingAgentsProjection(
            request_id=request_id,
            job_id=job_id,
            tradingagents_status=TradingAgentsProjectionMapper.to_internal_status(status),
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
