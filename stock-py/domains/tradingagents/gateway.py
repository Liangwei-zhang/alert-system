"""
Gateway for TradingAgents API integration.
"""

import os
from typing import Any, Dict, Optional
from urllib.parse import quote

from httpx import AsyncClient

from domains.tradingagents.schemas import SubmitTradingAgentsRequest
from infra.core.config import get_settings
from infra.http.http_client import get_http_client_factory


class TradingAgentsGateway:
    """Gateway for submitting jobs and polling results from TradingAgents API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_seconds: int = 30,
    ):
        settings = get_settings()
        configured_base_url = base_url or settings.tradingagents_base_url
        if not configured_base_url:
            configured_base_url = os.getenv("TRADINGAGENTS_BASE_URL", "http://127.0.0.1:8020")
        self.base_url = configured_base_url.rstrip("/")
        self.api_key = api_key if api_key is not None else settings.tradingagents_api_key
        if not self.api_key:
            self.api_key = os.getenv("TRADINGAGENTS_API_KEY", "")
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
            # TradingAgents async endpoint expects YYYY-MM-DD date strings.
            "analysis_date": request.analysis_date.date().isoformat(),
        }

        if request.selected_analysts:
            payload["selected_analysts"] = request.selected_analysts
        if request.debug is not None:
            payload["debug"] = request.debug
        if request.config_overrides:
            payload["config_overrides"] = request.config_overrides
        if request.publish_video is not None:
            payload["publish_video"] = request.publish_video
        if request.video_privacy_status:
            payload["video_privacy_status"] = request.video_privacy_status

        client = await self._get_client()
        response = await client.post(
            f"{self.base_url}/jobs",
            json=payload,
            headers=self.build_headers(),
            timeout=self.timeout_seconds,
        )
        if response.status_code in {200, 202}:
            data = response.json()
            return {
                "success": True,
                "job_id": data.get("job_id"),
                "status": data.get("status", "queued"),
                "http_status": response.status_code,
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
        request_id: str,
        include_full_result_payload: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Poll for compact stock-result projection by request ID.

        Returns:
            Dict with projection payload and HTTP status hints, None if request is unknown
        """
        encoded_request_id = quote(request_id, safe="")
        client = await self._get_client()
        response = await client.get(
            f"{self.base_url}/jobs/by-request/{encoded_request_id}/stock-result",
            params={
                "include_full_result_payload": "true" if include_full_result_payload else "false"
            },
            headers=self.build_headers(),
            timeout=self.timeout_seconds,
        )
        if response.status_code == 404:
            return None
        if response.status_code in {200, 202, 409}:
            data = response.json()
            if not isinstance(data, dict):
                data = {"result_payload": data}
            if "request_id" not in data:
                data["request_id"] = request_id
            data["http_status"] = response.status_code
            if "status" not in data and isinstance(data.get("tradingagents_status"), str):
                data["status"] = data["tradingagents_status"]
            return data
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
            f"{self.base_url}/jobs/{job_id}",
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
            f"{self.base_url}/jobs/{job_id}/cancel",
            headers=self.build_headers(),
            timeout=self.timeout_seconds,
        )
        return response.status_code in {200, 202}


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
