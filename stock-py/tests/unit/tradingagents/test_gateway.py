import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from domains.tradingagents.gateway import TradingAgentsGateway
from domains.tradingagents.schemas import SubmitTradingAgentsRequest


class FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return dict(self._payload)


class FakeClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls = []

    async def post(self, url: str, **kwargs):
        self.calls.append(("post", url, kwargs))
        return self.responses.pop(0)

    async def get(self, url: str, **kwargs):
        self.calls.append(("get", url, kwargs))
        return self.responses.pop(0)


class FakeHttpClientFactory:
    def __init__(self, client: FakeClient) -> None:
        self.client = client
        self.external_requests = 0

    async def get_external_client(self) -> FakeClient:
        self.external_requests += 1
        return self.client


class TradingAgentsGatewayTest(unittest.IsolatedAsyncioTestCase):
    async def test_submit_job_uses_shared_external_client(self) -> None:
        client = FakeClient(
            [FakeResponse(200, payload={"job_id": "job-123", "status": "submitted"})]
        )
        factory = FakeHttpClientFactory(client)
        gateway = TradingAgentsGateway(
            base_url="https://tradingagents.example",
            api_key="secret-key",
            timeout_seconds=12,
        )
        request = SubmitTradingAgentsRequest(
            request_id="req-1",
            ticker="AAPL",
            analysis_date=datetime(2026, 4, 4, tzinfo=UTC),
            trigger_type="manual",
            selected_analysts=["alpha"],
            trigger_context={"source": "test"},
        )

        with patch("domains.tradingagents.gateway.get_http_client_factory", return_value=factory):
            result = await gateway.submit_job(request)

        self.assertEqual(result, {"success": True, "job_id": "job-123", "status": "submitted"})
        self.assertEqual(factory.external_requests, 1)
        method, url, kwargs = client.calls[0]
        self.assertEqual(method, "post")
        self.assertEqual(url, "https://tradingagents.example/v1/jobs/submit")
        self.assertEqual(kwargs["timeout"], 12)
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret-key")
        self.assertEqual(kwargs["json"]["ticker"], "AAPL")
        self.assertEqual(kwargs["json"]["selected_analysts"], ["alpha"])

    async def test_get_stock_result_returns_none_on_not_found(self) -> None:
        client = FakeClient([FakeResponse(404, text="missing")])
        factory = FakeHttpClientFactory(client)
        gateway = TradingAgentsGateway(base_url="https://tradingagents.example")

        with patch("domains.tradingagents.gateway.get_http_client_factory", return_value=factory):
            result = await gateway.get_stock_result("job-missing")

        self.assertIsNone(result)
        self.assertEqual(factory.external_requests, 1)
        method, url, kwargs = client.calls[0]
        self.assertEqual(method, "get")
        self.assertEqual(url, "https://tradingagents.example/v1/jobs/job-missing/result")
        self.assertIn("headers", kwargs)


if __name__ == "__main__":
    unittest.main()
