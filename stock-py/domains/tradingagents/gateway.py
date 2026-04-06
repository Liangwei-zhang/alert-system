"""
Gateway for TradingAgents API integration.
"""

import os
from typing import Any, Dict, Optional

from httpx import AsyncClient

from domains.tradingagents.schemas import SubmitTradingAgentsRequest
from infra.http.http_client import get_http_client_factory


class TradingAgentsGateway:
    """Gateway for submitting jobs and polling results from TradingAgents API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_seconds: int = 30,
    ):
        self.base_url = base_url or os.getenv(
            "TRADINGAGENTS_BASE_URL", "https://api.tradingagents.com"
        )
        self.api_key = api_key or os.getenv("TRADINGAGENTS_API_KEY", "")
        self.timeout_seconds = timeout_seconds

    async def _get_client(self) -> AsyncClient:
        return await get_http_client_factory().get_external_client()

    def build_headers(self) -> Dict[str, str]:
        """Build HTTP headers for API requests."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def submit_job(
        self,
        request: SubmitTradingAgentsRequest,
    ) -> Dict[str, Any]:
        """
        Submit an analysis job to TradingAgents API.

        Returns:
            Dict with job_id and submission details
        """
        payload = {
            "request_id": request.request_id,
            "ticker": request.ticker,
            "analysis_date": request.analysis_date.isoformat(),
            "trigger_type": request.trigger_type,
        }

        if request.selected_analysts:
            payload["selected_analysts"] = request.selected_analysts
        if request.trigger_context:
            payload["trigger_context"] = request.trigger_context

        client = await self._get_client()
        response = await client.post(
            f"{self.base_url}/v1/jobs/submit",
            json=payload,
            headers=self.build_headers(),
            timeout=self.timeout_seconds,
        )
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "job_id": data.get("job_id"),
                "status": data.get("status", "submitted"),
            }
        if response.status_code == 429:
            raise TradingAgentsRateLimitError("Rate limited by TradingAgents API")
        if response.status_code == 500:
            raise TradingAgentsServerError(f"Server error: {response.text}")
        raise TradingAgentsApiError(
            f"Failed to submit job: {response.status_code} - {response.text}"
        )

    async def get_stock_result(
        self,
        job_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Poll for job result from TradingAgents API.

        Returns:
            Dict with job status and result if completed, None if still running
        """
        client = await self._get_client()
        response = await client.get(
            f"{self.base_url}/v1/jobs/{job_id}/result",
            headers=self.build_headers(),
            timeout=self.timeout_seconds,
        )
        if response.status_code == 200:
            return response.json()
        if response.status_code == 404:
            return None
        if response.status_code == 429:
            raise TradingAgentsRateLimitError("Rate limited by TradingAgents API")
        if response.status_code == 500:
            raise TradingAgentsServerError(f"Server error: {response.text}")
        raise TradingAgentsApiError(
            f"Failed to get result: {response.status_code} - {response.text}"
        )

    async def check_job_status(
        self,
        job_id: str,
    ) -> Dict[str, Any]:
        """
        Check job status without getting full result.

        Returns:
            Dict with status information
        """
        client = await self._get_client()
        response = await client.get(
            f"{self.base_url}/v1/jobs/{job_id}/status",
            headers=self.build_headers(),
            timeout=self.timeout_seconds,
        )
        if response.status_code == 200:
            return response.json()
        if response.status_code == 404:
            return {"status": "not_found", "job_id": job_id}
        raise TradingAgentsApiError(
            f"Failed to check status: {response.status_code} - {response.text}"
        )

    async def cancel_job(
        self,
        job_id: str,
    ) -> bool:
        """Cancel a running job."""
        client = await self._get_client()
        response = await client.post(
            f"{self.base_url}/v1/jobs/{job_id}/cancel",
            headers=self.build_headers(),
            timeout=self.timeout_seconds,
        )
        return response.status_code == 200


class TradingAgentsApiError(Exception):
    """Base exception for TradingAgents API errors."""

    pass


class TradingAgentsRateLimitError(TradingAgentsApiError):
    """Exception for rate limit errors."""

    pass


class TradingAgentsServerError(TradingAgentsApiError):
    """Exception for server errors."""

    pass


class TradingAgentsNotFoundError(TradingAgentsApiError):
    """Exception for not found errors."""

    pass
