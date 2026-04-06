from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.admin_api.dependencies import get_tradingagents_read_model_service
from apps.admin_api.routers import tradingagents as tradingagents_router
from domains.analytics.schemas import TradingAgentsMetricsResponse
from infra.db.session import get_db_session


class FakeTradingAgentsRepository:
    list_records = []
    total = 0
    records_by_request_id = {}
    delayed_records = []
    calls: dict[str, list | dict] = {}

    def __init__(self, db) -> None:
        self.db = db

    @classmethod
    def reset(cls) -> None:
        cls.list_records = []
        cls.total = 0
        cls.records_by_request_id = {}
        cls.delayed_records = []
        cls.calls = {
            "list_analyses": [],
            "count_analyses": [],
            "get_by_request_id": [],
            "list_delayed": [],
            "mark_completed": [],
            "mark_failed": [],
            "mark_delayed": [],
        }

    async def list_analyses(self, **kwargs):
        self.calls["list_analyses"].append(kwargs)
        return list(self.list_records)

    async def count_analyses(self, status=None, ticker=None) -> int:
        self.calls["count_analyses"].append({"status": status, "ticker": ticker})
        return self.total

    async def get_by_request_id(self, request_id: str):
        self.calls["get_by_request_id"].append(request_id)
        return self.records_by_request_id.get(request_id)

    async def list_delayed(self, delayed_threshold_minutes: int = 30):
        self.calls["list_delayed"].append(delayed_threshold_minutes)
        return list(self.delayed_records)

    async def mark_completed(
        self,
        request_id: str,
        final_action: str,
        decision_summary=None,
        result_payload=None,
    ):
        self.calls["mark_completed"].append(
            {
                "request_id": request_id,
                "final_action": final_action,
                "decision_summary": decision_summary,
                "result_payload": result_payload,
            }
        )

    async def mark_failed(self, request_id: str, error_message=None):
        self.calls["mark_failed"].append({"request_id": request_id, "error_message": error_message})

    async def mark_delayed(self, request_id: str):
        self.calls["mark_delayed"].append(request_id)


class FakeTradingAgentsGateway:
    results_by_job_id: dict[str, dict] = {}
    errors_by_job_id: dict[str, Exception] = {}
    calls: list[str] = []

    @classmethod
    def reset(cls) -> None:
        cls.results_by_job_id = {}
        cls.errors_by_job_id = {}
        cls.calls = []

    async def get_stock_result(self, job_id: str):
        self.calls.append(job_id)
        if job_id in self.errors_by_job_id:
            raise self.errors_by_job_id[job_id]
        return self.results_by_job_id.get(job_id)


class FakeTradingAgentsReadModelService:
    response = TradingAgentsMetricsResponse(window_hours=24)
    calls: list[int] = []

    @classmethod
    def reset(cls) -> None:
        cls.response = TradingAgentsMetricsResponse(window_hours=24)
        cls.calls = []

    async def build_tradingagents_view(self, window_hours: int):
        self.calls.append(window_hours)
        return self.response


class AdminTradingAgentsRouterIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        FakeTradingAgentsRepository.reset()
        FakeTradingAgentsGateway.reset()
        FakeTradingAgentsReadModelService.reset()

        self.app = FastAPI()
        self.app.include_router(tradingagents_router.router)

        async def override_db_session():
            yield object()

        async def override_tradingagents_service():
            return FakeTradingAgentsReadModelService()

        self.app.dependency_overrides[get_db_session] = override_db_session
        self.app.dependency_overrides[get_tradingagents_read_model_service] = (
            override_tradingagents_service
        )

        self.repository_patch = patch.object(
            tradingagents_router,
            "TradingAgentsRepository",
            FakeTradingAgentsRepository,
        )
        self.gateway_patch = patch(
            "domains.tradingagents.gateway.TradingAgentsGateway",
            FakeTradingAgentsGateway,
        )
        self.repository_patch.start()
        self.gateway_patch.start()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.repository_patch.stop()
        self.gateway_patch.stop()

    def test_admin_routes_return_current_records_and_stats(self) -> None:
        now = datetime(2026, 4, 5, tzinfo=timezone.utc)
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

        FakeTradingAgentsRepository.list_records = [analysis_record]
        FakeTradingAgentsRepository.total = 1
        FakeTradingAgentsRepository.records_by_request_id = {"req-1": analysis_record}
        FakeTradingAgentsRepository.delayed_records = [delayed_record]
        FakeTradingAgentsGateway.results_by_job_id = {
            "job-delayed": {
                "status": "completed",
                "final_action": "buy",
                "decision_summary": "Recovered by polling",
            }
        }
        FakeTradingAgentsReadModelService.response = TradingAgentsMetricsResponse(
            window_hours=24,
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

        list_response = self.client.get(
            "/v1/admin/tradingagents/analyses",
            params={"status": "completed", "ticker": "AAPL", "limit": 50, "offset": 0},
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(
            list_response.json(),
            {
                "data": [
                    {
                        "id": 1,
                        "request_id": "req-1",
                        "job_id": "job-1",
                        "ticker": "AAPL",
                        "analysis_date": "2026-04-05T00:00:00Z",
                        "selected_analysts": ["alpha", "beta"],
                        "trigger_type": "manual",
                        "trigger_context": {"source": "dashboard"},
                        "tradingagents_status": "completed",
                        "final_action": "buy",
                        "decision_summary": "Bullish setup",
                        "submitted_at": "2026-04-05T00:00:00Z",
                        "completed_at": "2026-04-05T00:00:00Z",
                        "delayed_at": None,
                        "created_at": "2026-04-05T00:00:00Z",
                        "poll_count": 2,
                        "webhook_received": True,
                    }
                ],
                "total": 1,
                "limit": 50,
                "offset": 0,
                "has_more": False,
            },
        )

        get_response = self.client.get("/v1/admin/tradingagents/analyses/req-1")
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["request_id"], "req-1")

        reconcile_response = self.client.post(
            "/v1/admin/tradingagents/reconcile-delayed",
            params={"delayed_threshold_minutes": 30},
        )
        self.assertEqual(reconcile_response.status_code, 200)
        self.assertEqual(
            reconcile_response.json(),
            {
                "processed_count": 1,
                "reconciled_count": 1,
                "failed_count": 0,
                "message": "Processed 1 delayed jobs, reconciled 1, failed 0",
            },
        )

        stats_response = self.client.get("/v1/admin/tradingagents/stats")
        self.assertEqual(stats_response.status_code, 200)
        self.assertEqual(
            stats_response.json(),
            {
                "total": 12,
                "by_status": {"pending": 2, "completed": 8, "failed": 2},
                "last_24h": 12,
                "completed_total": 8,
                "failed_total": 2,
                "open_total": 2,
                "terminal_total": 10,
                "success_rate": 80.0,
                "avg_latency_seconds": 14.5,
                "by_final_action": {"buy": 5, "hold": 3, "sell": 2},
            },
        )

        self.assertEqual(
            FakeTradingAgentsRepository.calls["list_analyses"],
            [
                {
                    "status": "completed",
                    "ticker": "AAPL",
                    "trigger_type": None,
                    "from_date": None,
                    "to_date": None,
                    "limit": 50,
                    "offset": 0,
                }
            ],
        )
        self.assertEqual(
            FakeTradingAgentsRepository.calls["count_analyses"],
            [{"status": "completed", "ticker": "AAPL"}],
        )
        self.assertEqual(FakeTradingAgentsRepository.calls["get_by_request_id"], ["req-1"])
        self.assertEqual(FakeTradingAgentsRepository.calls["list_delayed"], [30])
        self.assertEqual(FakeTradingAgentsGateway.calls, ["job-delayed"])
        self.assertEqual(
            FakeTradingAgentsRepository.calls["mark_completed"],
            [
                {
                    "request_id": "req-delayed",
                    "final_action": "buy",
                    "decision_summary": "Recovered by polling",
                    "result_payload": {
                        "status": "completed",
                        "final_action": "buy",
                        "decision_summary": "Recovered by polling",
                    },
                }
            ],
        )
        self.assertEqual(FakeTradingAgentsReadModelService.calls, [24])

    def test_get_analysis_404_and_reconcile_failure_paths(self) -> None:
        FakeTradingAgentsRepository.delayed_records = [
            SimpleNamespace(request_id="req-failed", job_id="job-failed"),
            SimpleNamespace(request_id="req-running", job_id="job-running"),
            SimpleNamespace(request_id="req-error", job_id="job-error"),
            SimpleNamespace(request_id="req-missing-job", job_id=None),
        ]
        FakeTradingAgentsGateway.results_by_job_id = {
            "job-failed": {"status": "failed", "error": "provider failed"},
            "job-running": {"status": "running"},
        }
        FakeTradingAgentsGateway.errors_by_job_id = {"job-error": RuntimeError("gateway timeout")}

        get_response = self.client.get("/v1/admin/tradingagents/analyses/missing")
        self.assertEqual(get_response.status_code, 404)
        self.assertEqual(get_response.json(), {"detail": "Analysis not found"})

        reconcile_response = self.client.post(
            "/v1/admin/tradingagents/reconcile-delayed",
            params={"delayed_threshold_minutes": 45},
        )
        self.assertEqual(reconcile_response.status_code, 200)
        self.assertEqual(
            reconcile_response.json(),
            {
                "processed_count": 3,
                "reconciled_count": 1,
                "failed_count": 1,
                "message": "Processed 3 delayed jobs, reconciled 1, failed 1",
            },
        )

        self.assertEqual(FakeTradingAgentsRepository.calls["get_by_request_id"], ["missing"])
        self.assertEqual(FakeTradingAgentsRepository.calls["list_delayed"], [45])
        self.assertEqual(
            FakeTradingAgentsGateway.calls,
            ["job-failed", "job-running", "job-error"],
        )
        self.assertEqual(
            FakeTradingAgentsRepository.calls["mark_failed"],
            [{"request_id": "req-failed", "error_message": "provider failed"}],
        )
        self.assertEqual(
            FakeTradingAgentsRepository.calls["mark_delayed"],
            ["req-running"],
        )


if __name__ == "__main__":
    unittest.main()
