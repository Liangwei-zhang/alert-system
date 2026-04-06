from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from domains.analytics.schemas import TradingAgentsMetricsResponse
from domains.analytics.tradingagents_read_model_service import TradingAgentsReadModelService
from domains.tradingagents.gateway import TradingAgentsGateway
from domains.tradingagents.orchestrator import TradingAgentsOrchestrator
from domains.tradingagents.repository import TradingAgentsRepository
from domains.tradingagents.schemas import SubmitTradingAgentsResponse
from domains.tradingagents.webhook_service import TradingAgentsWebhookService
from tests.helpers.app_client import AdminApiClient, PublicApiClient


def test_tradingagents_flow(
    public_api_client: PublicApiClient,
    authenticated_admin_api_client: AdminApiClient,
    monkeypatch,
) -> None:
    now = datetime(2026, 4, 4, tzinfo=timezone.utc)
    calls: dict[str, object] = {}
    analysis_record = SimpleNamespace(
        id=1,
        request_id="req-1",
        job_id="job-1",
        ticker="AAPL",
        analysis_date=now,
        selected_analysts='["alpha","beta"]',
        trigger_type="manual",
        trigger_context='{"source":"dashboard"}',
        tradingagents_status="completed",
        final_action="buy",
        decision_summary="Bullish setup",
        submitted_at=now,
        completed_at=now,
        delayed_at=None,
        created_at=now,
        poll_count=2,
        webhook_received=True,
    )
    delayed_record = SimpleNamespace(request_id="req-delayed", job_id="job-delayed")

    async def fake_submit_direct(self, request) -> SubmitTradingAgentsResponse:
        calls["submit_direct"] = request.model_dump(mode="json")
        return SubmitTradingAgentsResponse(
            request_id=request.request_id,
            job_id="job-1",
            status="submitted",
            message="Job submitted successfully",
        )

    async def fake_handle_terminal_event(self, payload: dict) -> dict:
        calls["handle_terminal_event"] = payload
        return {"success": True, "request_id": payload["request_id"], "status": "processed"}

    async def fake_list_analyses(self, **kwargs):
        calls["list_analyses"] = kwargs
        return [analysis_record]

    async def fake_count_analyses(self, status=None, ticker=None) -> int:
        calls["count_analyses"] = {"status": status, "ticker": ticker}
        return 1

    async def fake_get_by_request_id(self, request_id: str):
        calls.setdefault("get_by_request_id", []).append(request_id)
        if request_id == "req-1":
            return analysis_record
        return None

    async def fake_list_delayed(self, delayed_threshold_minutes: int = 30):
        calls["list_delayed"] = delayed_threshold_minutes
        return [delayed_record]

    async def fake_get_stock_result(self, job_id: str):
        calls["get_stock_result"] = job_id
        return {
            "status": "completed",
            "final_action": "buy",
            "decision_summary": "Recovered by polling",
        }

    async def fake_mark_completed(
        self, request_id: str, final_action: str, decision_summary=None, result_payload=None
    ):
        calls["mark_completed"] = {
            "request_id": request_id,
            "final_action": final_action,
            "decision_summary": decision_summary,
            "result_payload": result_payload,
        }
        return analysis_record

    async def fake_mark_failed(self, request_id: str, error_message=None):
        calls["mark_failed"] = {"request_id": request_id, "error_message": error_message}
        return analysis_record

    async def fake_mark_delayed(self, request_id: str):
        calls["mark_delayed"] = request_id
        return analysis_record

    async def fake_build_tradingagents_view(
        self, window_hours: int
    ) -> TradingAgentsMetricsResponse:
        calls["build_tradingagents_view"] = window_hours
        return TradingAgentsMetricsResponse(
            window_hours=window_hours,
            requested_total=12,
            terminal_total=10,
            completed_total=8,
            failed_total=2,
            open_total=2,
            success_rate=80.0,
            avg_latency_seconds=14.5,
            by_status={"pending": 2, "completed": 8, "failed": 2},
            by_final_action={"buy": 5, "hold": 3, "sell": 2},
        )

    monkeypatch.setattr(TradingAgentsOrchestrator, "submit_direct", fake_submit_direct)
    monkeypatch.setattr(
        TradingAgentsWebhookService, "handle_terminal_event", fake_handle_terminal_event
    )
    monkeypatch.setattr(TradingAgentsRepository, "list_analyses", fake_list_analyses)
    monkeypatch.setattr(TradingAgentsRepository, "count_analyses", fake_count_analyses)
    monkeypatch.setattr(TradingAgentsRepository, "get_by_request_id", fake_get_by_request_id)
    monkeypatch.setattr(TradingAgentsRepository, "list_delayed", fake_list_delayed)
    monkeypatch.setattr(TradingAgentsRepository, "mark_completed", fake_mark_completed)
    monkeypatch.setattr(TradingAgentsRepository, "mark_failed", fake_mark_failed)
    monkeypatch.setattr(TradingAgentsRepository, "mark_delayed", fake_mark_delayed)
    monkeypatch.setattr(TradingAgentsGateway, "get_stock_result", fake_get_stock_result)
    monkeypatch.setattr(
        TradingAgentsReadModelService, "build_tradingagents_view", fake_build_tradingagents_view
    )

    submit_result = public_api_client.post(
        "/v1/internal/tradingagents/submit",
        json={
            "request_id": "req-1",
            "ticker": "aapl",
            "analysis_date": "2026-04-04T00:00:00Z",
            "selected_analysts": ["alpha", "beta"],
            "trigger_type": "manual",
            "trigger_context": {"source": "dashboard"},
        },
    )
    assert submit_result.status_code == 200
    assert submit_result.json() == {
        "request_id": "req-1",
        "job_id": "job-1",
        "status": "submitted",
        "message": "Job submitted successfully",
    }

    webhook_result = public_api_client.post(
        "/v1/internal/tradingagents/job-terminal",
        json={
            "request_id": "req-1",
            "job_id": "job-1",
            "status": "completed",
            "final_action": "buy",
            "decision_summary": "Bullish setup",
            "result_payload": {"score": 0.92},
            "timestamp": "2026-04-04T00:05:00Z",
        },
    )
    assert webhook_result.status_code == 200
    assert webhook_result.json() == {"success": True, "request_id": "req-1", "status": "processed"}

    list_result = authenticated_admin_api_client.get(
        "/v1/admin/tradingagents/analyses",
        params={"status": "completed", "ticker": "AAPL", "limit": 50, "offset": 0},
    )
    assert list_result.status_code == 200
    assert list_result.json()["total"] == 1
    assert list_result.json()["data"][0]["request_id"] == "req-1"

    get_result = authenticated_admin_api_client.get("/v1/admin/tradingagents/analyses/req-1")
    assert get_result.status_code == 200
    assert get_result.json()["request_id"] == "req-1"

    reconcile_result = authenticated_admin_api_client.post(
        "/v1/admin/tradingagents/reconcile-delayed",
        params={"delayed_threshold_minutes": 30},
    )
    assert reconcile_result.status_code == 200
    assert reconcile_result.json()["processed_count"] == 1
    assert reconcile_result.json()["reconciled_count"] == 1

    stats_result = authenticated_admin_api_client.get("/v1/admin/tradingagents/stats")
    assert stats_result.status_code == 200
    assert stats_result.json()["total"] == 12
    assert stats_result.json()["completed_total"] == 8
    assert stats_result.json()["by_final_action"] == {"buy": 5, "hold": 3, "sell": 2}

    assert calls["submit_direct"] == {
        "request_id": "req-1",
        "ticker": "AAPL",
        "analysis_date": "2026-04-04T00:00:00Z",
        "selected_analysts": ["alpha", "beta"],
        "trigger_type": "manual",
        "trigger_context": {"source": "dashboard"},
    }
    assert calls["handle_terminal_event"] == {
        "request_id": "req-1",
        "job_id": "job-1",
        "status": "completed",
        "final_action": "buy",
        "decision_summary": "Bullish setup",
        "result_payload": {"score": 0.92},
        "timestamp": "2026-04-04T00:05:00Z",
    }
    assert calls["list_analyses"] == {
        "status": "completed",
        "ticker": "AAPL",
        "trigger_type": None,
        "from_date": None,
        "to_date": None,
        "limit": 50,
        "offset": 0,
    }
    assert calls["count_analyses"] == {"status": "completed", "ticker": "AAPL"}
    assert calls["get_by_request_id"] == ["req-1"]
    assert calls["list_delayed"] == 30
    assert calls["get_stock_result"] == "job-delayed"
    assert calls["mark_completed"] == {
        "request_id": "req-delayed",
        "final_action": "buy",
        "decision_summary": "Recovered by polling",
        "result_payload": {
            "status": "completed",
            "final_action": "buy",
            "decision_summary": "Recovered by polling",
        },
    }
    assert calls["build_tradingagents_view"] == 24
