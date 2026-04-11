import asyncio
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from domains.tradingagents.gateway import TradingAgentsApiError, TradingAgentsRateLimitError
from domains.tradingagents.orchestrator import TradingAgentsOrchestrator
from domains.tradingagents.schemas import SubmitTradingAgentsRequest


class FakeTradingAgentsRepository:
    def __init__(self, existing=None) -> None:
        self.existing = existing
        self.insert_calls: list[dict] = []
        self.insert_if_absent_calls: list[dict] = []
        self.mark_submitted_calls: list[dict] = []
        self.increment_poll_count_calls: list[str] = []
        self.update_projection_calls: list[dict] = []
        self.mark_completed_calls: list[dict] = []
        self.mark_failed_calls: list[dict] = []
        self.lookup_count = 0

    async def get_by_request_id(self, request_id: str):
        self.lookup_count += 1
        return self.existing

    async def insert_accepted(
        self,
        request_id: str,
        ticker: str,
        analysis_date: datetime,
        trigger_type: str,
        selected_analysts=None,
        trigger_context=None,
    ):
        record = SimpleNamespace(request_id=request_id, job_id=None)
        self.insert_calls.append(
            {
                "request_id": request_id,
                "ticker": ticker,
                "analysis_date": analysis_date,
                "trigger_type": trigger_type,
                "selected_analysts": selected_analysts,
                "trigger_context": trigger_context,
            }
        )
        self.existing = record
        return record

    async def insert_accepted_if_absent(
        self,
        request_id: str,
        ticker: str,
        analysis_date: datetime,
        trigger_type: str,
        selected_analysts=None,
        trigger_context=None,
    ):
        self.insert_if_absent_calls.append(
            {
                "request_id": request_id,
                "ticker": ticker,
                "analysis_date": analysis_date,
                "trigger_type": trigger_type,
                "selected_analysts": selected_analysts,
                "trigger_context": trigger_context,
            }
        )
        if self.existing is not None:
            return self.existing, False

        record = SimpleNamespace(
            request_id=request_id,
            job_id=None,
            tradingagents_status=SimpleNamespace(value="pending"),
        )
        self.existing = record
        return None, True

    async def mark_submitted(self, request_id: str, job_id: str):
        self.mark_submitted_calls.append({"request_id": request_id, "job_id": job_id})
        if self.existing is not None:
            self.existing.job_id = job_id
        return self.existing

    async def increment_poll_count(self, request_id: str) -> None:
        self.increment_poll_count_calls.append(request_id)

    async def update_projection(self, **kwargs):
        self.update_projection_calls.append(kwargs)
        return self.existing

    async def mark_completed(
        self, request_id: str, final_action: str, decision_summary=None, result_payload=None
    ):
        self.mark_completed_calls.append(
            {
                "request_id": request_id,
                "final_action": final_action,
                "decision_summary": decision_summary,
                "result_payload": result_payload,
            }
        )
        return self.existing

    async def mark_failed(self, request_id: str, error_message=None):
        self.mark_failed_calls.append({"request_id": request_id, "error_message": error_message})
        return self.existing


class FakeGateway:
    def __init__(self, submit_result=None, submit_error=None, poll_result=None) -> None:
        self.submit_result = submit_result
        self.submit_error = submit_error
        self.poll_result = poll_result
        self.submit_calls: list[SubmitTradingAgentsRequest] = []
        self.poll_calls: list[str] = []

    async def submit_job(self, request: SubmitTradingAgentsRequest):
        self.submit_calls.append(request)
        if self.submit_error is not None:
            raise self.submit_error
        return self.submit_result or {}

    async def get_stock_result(
        self,
        request_id: str,
        include_full_result_payload: bool = False,
    ):
        self.poll_calls.append(request_id)
        return self.poll_result


class TradingAgentsOrchestratorTest(unittest.TestCase):
    def _build_orchestrator(self, repository: FakeTradingAgentsRepository, gateway: FakeGateway):
        orchestrator = TradingAgentsOrchestrator(session=SimpleNamespace(), gateway=gateway)
        orchestrator.repository = repository
        published_events: list[dict] = []

        async def fake_publish_requested_event(**kwargs) -> None:
            published_events.append(kwargs)

        orchestrator._publish_requested_event = fake_publish_requested_event
        return orchestrator, published_events

    def test_submit_direct_returns_existing_request_without_resubmitting(self) -> None:
        repository = FakeTradingAgentsRepository(
            existing=SimpleNamespace(
                job_id="job-existing", tradingagents_status=SimpleNamespace(value="submitted")
            )
        )
        gateway = FakeGateway()
        orchestrator, published_events = self._build_orchestrator(repository, gateway)
        request = SubmitTradingAgentsRequest(
            request_id="req-existing",
            ticker="aapl",
            analysis_date=datetime(2026, 4, 4, tzinfo=timezone.utc),
            selected_analysts=["alpha"],
            trigger_type="manual",
            trigger_context={"source": "dashboard"},
        )

        response = asyncio.run(orchestrator.submit_direct(request))

        self.assertEqual(response.request_id, "req-existing")
        self.assertEqual(response.job_id, "job-existing")
        self.assertEqual(response.status, "submitted")
        self.assertEqual(response.message, "Request already exists")
        self.assertEqual(repository.insert_calls, [])
        self.assertEqual(repository.insert_if_absent_calls[0]["ticker"], "AAPL")
        self.assertEqual(gateway.submit_calls, [])
        self.assertEqual(published_events, [])

    def test_submit_direct_marks_job_submitted_and_publishes_event(self) -> None:
        repository = FakeTradingAgentsRepository()
        gateway = FakeGateway(submit_result={"job_id": "job-123", "status": "submitted"})
        orchestrator, published_events = self._build_orchestrator(repository, gateway)
        request = SubmitTradingAgentsRequest(
            request_id="req-1",
            ticker="aapl",
            analysis_date=datetime(2026, 4, 4, tzinfo=timezone.utc),
            selected_analysts=["alpha", "beta"],
            trigger_type="manual",
            trigger_context={"source": "dashboard"},
        )

        response = asyncio.run(orchestrator.submit_direct(request))

        self.assertEqual(response.status, "submitted")
        self.assertEqual(response.job_id, "job-123")
        self.assertEqual(repository.insert_if_absent_calls[0]["ticker"], "AAPL")
        self.assertEqual(repository.insert_calls, [])
        self.assertEqual(
            repository.mark_submitted_calls, [{"request_id": "req-1", "job_id": "job-123"}]
        )
        self.assertEqual(len(gateway.submit_calls), 1)
        self.assertEqual(gateway.submit_calls[0].ticker, "AAPL")
        self.assertEqual(len(published_events), 1)
        self.assertEqual(published_events[0]["request_id"], "req-1")
        self.assertEqual(published_events[0]["status"], "accepted")

    def test_submit_direct_returns_pending_when_rate_limited(self) -> None:
        repository = FakeTradingAgentsRepository()
        gateway = FakeGateway(submit_error=TradingAgentsRateLimitError("slow down"))
        orchestrator, published_events = self._build_orchestrator(repository, gateway)
        request = SubmitTradingAgentsRequest(
            request_id="req-rate-limit",
            ticker="msft",
            analysis_date=datetime(2026, 4, 4, tzinfo=timezone.utc),
            selected_analysts=None,
            trigger_type="scanner",
            trigger_context=None,
        )

        response = asyncio.run(orchestrator.submit_direct(request))

        self.assertEqual(response.status, "pending")
        self.assertIsNone(response.job_id)
        self.assertEqual(repository.mark_submitted_calls, [])
        self.assertEqual(len(repository.insert_if_absent_calls), 1)
        self.assertEqual(repository.insert_calls, [])
        self.assertEqual(len(published_events), 1)

    def test_submit_direct_returns_failed_when_gateway_errors(self) -> None:
        repository = FakeTradingAgentsRepository()
        gateway = FakeGateway(submit_error=TradingAgentsApiError("server exploded"))
        orchestrator, _ = self._build_orchestrator(repository, gateway)
        request = SubmitTradingAgentsRequest(
            request_id="req-failed",
            ticker="nvda",
            analysis_date=datetime(2026, 4, 4, tzinfo=timezone.utc),
            selected_analysts=None,
            trigger_type="manual",
            trigger_context={"source": "qa"},
        )

        response = asyncio.run(orchestrator.submit_direct(request))

        self.assertEqual(response.status, "failed")
        self.assertIn("server exploded", response.message)
        self.assertEqual(repository.mark_submitted_calls, [])
        self.assertEqual(len(repository.insert_if_absent_calls), 1)

    def test_poll_and_update_marks_completed_projection(self) -> None:
        repository = FakeTradingAgentsRepository(
            existing=SimpleNamespace(request_id="req-poll", job_id="job-poll")
        )
        gateway = FakeGateway(
            poll_result={
                "status": "completed",
                "final_action": "buy",
                "decision_summary": "Strong bullish alignment",
                "result": {"score": 0.91},
            }
        )
        orchestrator, _ = self._build_orchestrator(repository, gateway)

        projection = asyncio.run(orchestrator.poll_and_update("req-poll"))

        self.assertIsNotNone(projection)
        self.assertEqual(projection.request_id, "req-poll")
        self.assertEqual(projection.tradingagents_status, "completed")
        self.assertEqual(repository.increment_poll_count_calls, ["req-poll"])
        self.assertEqual(gateway.poll_calls, ["req-poll"])
        self.assertEqual(
            repository.update_projection_calls,
            [
                {
                    "request_id": "req-poll",
                    "job_id": "job-poll",
                    "tradingagents_status": "completed",
                    "final_action": "buy",
                    "decision_summary": "Strong bullish alignment",
                    "result_payload": {"score": 0.91},
                }
            ],
        )
        self.assertEqual(
            repository.mark_completed_calls,
            [
                {
                    "request_id": "req-poll",
                    "final_action": "buy",
                    "decision_summary": "Strong bullish alignment",
                    "result_payload": {"score": 0.91},
                }
            ],
        )
        self.assertEqual(repository.mark_failed_calls, [])


if __name__ == "__main__":
    unittest.main()
