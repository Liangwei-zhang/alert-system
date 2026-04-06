from __future__ import annotations

import json
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.admin_api.routers import backtests as backtests_router
from apps.admin_api.routers import scanner as scanner_router
from infra.core.errors import register_exception_handlers
from infra.db.session import get_db_session


class FakeBacktestRepository:
    runs = []
    runs_by_id = {}
    rankings = []
    calls: dict[str, list] = {}

    def __init__(self, db) -> None:
        self.db = db

    @classmethod
    def reset(cls) -> None:
        cls.runs = []
        cls.runs_by_id = {}
        cls.rankings = []
        cls.calls = {
            "list_runs": [],
            "count_runs": [],
            "get_run": [],
            "list_latest_rankings": [],
        }

    @classmethod
    def _filter_runs(cls, *, status=None, strategy_name=None, timeframe=None, symbol=None):
        items = list(cls.runs)
        if status:
            items = [item for item in items if str(getattr(item, "status", "")) == status]
        if strategy_name:
            items = [item for item in items if item.strategy_name == strategy_name]
        if timeframe:
            items = [item for item in items if item.timeframe == timeframe]
        if symbol:
            items = [item for item in items if (item.symbol or "") == symbol.upper()]
        return items

    async def list_runs(self, **kwargs):
        self.calls["list_runs"].append(kwargs)
        items = self._filter_runs(
            status=kwargs.get("status"),
            strategy_name=kwargs.get("strategy_name"),
            timeframe=kwargs.get("timeframe"),
            symbol=kwargs.get("symbol"),
        )
        offset = int(kwargs.get("offset", 0) or 0)
        limit = int(kwargs.get("limit", len(items)) or len(items))
        return list(items[offset : offset + limit])

    async def count_runs(self, **kwargs):
        self.calls["count_runs"].append(kwargs)
        return len(
            self._filter_runs(
                status=kwargs.get("status"),
                strategy_name=kwargs.get("strategy_name"),
                timeframe=kwargs.get("timeframe"),
                symbol=kwargs.get("symbol"),
            )
        )

    async def get_run(self, run_id: int):
        self.calls["get_run"].append(run_id)
        return self.runs_by_id.get(run_id)

    async def list_latest_rankings(self, **kwargs):
        self.calls["list_latest_rankings"].append(kwargs)
        timeframe = kwargs.get("timeframe")
        items = list(self.rankings)
        if timeframe:
            items = [item for item in items if item.timeframe == timeframe]
        limit = int(kwargs.get("limit", len(items)) or len(items))
        return list(items[:limit])


class FakeBacktestService:
    calls = []
    return_value = {}

    def __init__(self, db) -> None:
        self.db = db

    @classmethod
    def reset(cls) -> None:
        cls.calls = []
        cls.return_value = {}

    async def refresh_rankings(
        self,
        *,
        symbols=None,
        strategy_names=None,
        windows=None,
        timeframe="1d",
    ):
        self.calls.append(
            {
                "symbols": list(symbols) if symbols is not None else None,
                "strategy_names": list(strategy_names) if strategy_names is not None else None,
                "windows": list(windows) if windows is not None else None,
                "timeframe": timeframe,
            }
        )
        return deepcopy(self.return_value)


class FakeScannerRunRepository:
    runs = []
    runs_by_id = {}
    decisions = []
    calls: dict[str, list] = {}

    def __init__(self, db) -> None:
        self.db = db

    @classmethod
    def reset(cls) -> None:
        cls.runs = []
        cls.runs_by_id = {}
        cls.decisions = []
        cls.calls = {
            "list_runs": [],
            "count_runs": [],
            "get_run": [],
            "list_decisions": [],
            "count_decisions": [],
        }

    @classmethod
    def _filter_runs(cls, *, status=None, bucket_id=None):
        items = list(cls.runs)
        if status:
            items = [item for item in items if item.status == status]
        if bucket_id is not None:
            items = [item for item in items if item.bucket_id == bucket_id]
        return items

    @classmethod
    def _filter_decisions(cls, *, run_id=None, symbol=None, decision=None, suppressed=None):
        items = list(cls.decisions)
        if run_id is not None:
            items = [item for item in items if item.run_id == run_id]
        if symbol:
            items = [item for item in items if item.symbol == symbol.upper()]
        if decision:
            items = [item for item in items if item.decision == decision]
        if suppressed is not None:
            items = [item for item in items if item.suppressed is suppressed]
        return items

    async def list_runs(self, **kwargs):
        self.calls["list_runs"].append(kwargs)
        items = self._filter_runs(status=kwargs.get("status"), bucket_id=kwargs.get("bucket_id"))
        offset = int(kwargs.get("offset", 0) or 0)
        limit = int(kwargs.get("limit", len(items)) or len(items))
        return list(items[offset : offset + limit])

    async def count_runs(self, **kwargs):
        self.calls["count_runs"].append(kwargs)
        return len(
            self._filter_runs(status=kwargs.get("status"), bucket_id=kwargs.get("bucket_id"))
        )

    async def get_run(self, run_id: int):
        self.calls["get_run"].append(run_id)
        return self.runs_by_id.get(run_id)

    async def list_decisions(self, **kwargs):
        self.calls["list_decisions"].append(kwargs)
        items = self._filter_decisions(
            run_id=kwargs.get("run_id"),
            symbol=kwargs.get("symbol"),
            decision=kwargs.get("decision"),
            suppressed=kwargs.get("suppressed"),
        )
        offset = int(kwargs.get("offset", 0) or 0)
        limit = int(kwargs.get("limit", len(items)) or len(items))
        return list(items[offset : offset + limit])

    async def count_decisions(self, **kwargs):
        self.calls["count_decisions"].append(kwargs)
        return len(
            self._filter_decisions(
                run_id=kwargs.get("run_id"),
                symbol=kwargs.get("symbol"),
                decision=kwargs.get("decision"),
                suppressed=kwargs.get("suppressed"),
            )
        )


class AdminBacktestsAndScannerRouterIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        FakeBacktestRepository.reset()
        FakeBacktestService.reset()
        FakeScannerRunRepository.reset()

        self.app = FastAPI()
        register_exception_handlers(self.app)
        self.app.include_router(backtests_router.router)
        self.app.include_router(scanner_router.router)

        async def override_db_session():
            yield object()

        self.app.dependency_overrides[get_db_session] = override_db_session

        self.backtest_repository_patch = patch.object(
            backtests_router,
            "BacktestRepository",
            FakeBacktestRepository,
        )
        self.backtest_service_patch = patch.object(
            backtests_router,
            "BacktestService",
            FakeBacktestService,
        )
        self.scanner_repository_patch = patch.object(
            scanner_router,
            "ScannerRunRepository",
            FakeScannerRunRepository,
        )
        self.backtest_repository_patch.start()
        self.backtest_service_patch.start()
        self.scanner_repository_patch.start()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.backtest_repository_patch.stop()
        self.backtest_service_patch.stop()
        self.scanner_repository_patch.stop()

    def test_backtests_routes_list_detail_and_refresh(self) -> None:
        now = datetime(2026, 4, 5, tzinfo=timezone.utc)
        run = SimpleNamespace(
            id=12,
            strategy_name="ranking_refresh",
            symbol="*",
            timeframe="1d",
            window_days=365,
            status="completed",
            summary=json.dumps({"ranking_count": 2, "top_strategy": "trend_following"}),
            metrics=json.dumps(
                {
                    "rankings": [
                        {"strategy_name": "trend_following", "score": 1.42},
                        {"strategy_name": "breakout", "score": 1.08},
                    ]
                }
            ),
            evidence=json.dumps({"strategies": ["trend_following", "breakout"]}),
            error_message=None,
            started_at=now - timedelta(minutes=30),
            completed_at=now - timedelta(minutes=28),
        )
        ranking_one = SimpleNamespace(
            id=101,
            strategy_name="trend_following",
            timeframe="1d",
            rank=1,
            score=1.42,
            degradation=0.11,
            symbols_covered=18,
            evidence=json.dumps({"best_window": 90}),
            as_of_date=now,
        )
        ranking_two = SimpleNamespace(
            id=102,
            strategy_name="breakout",
            timeframe="1d",
            rank=2,
            score=1.08,
            degradation=0.18,
            symbols_covered=18,
            evidence=json.dumps({"best_window": 30}),
            as_of_date=now,
        )

        FakeBacktestRepository.runs = [run]
        FakeBacktestRepository.runs_by_id = {12: run}
        FakeBacktestRepository.rankings = [ranking_one, ranking_two]
        FakeBacktestService.return_value = {
            "run_id": 18,
            "ranking_count": 2,
            "rankings": [
                {
                    "strategy_name": "trend_following",
                    "timeframe": "1d",
                    "rank": 1,
                    "score": 1.42,
                    "degradation": 0.11,
                    "symbols_covered": 18,
                    "evidence": {"best_window": 90},
                },
                {
                    "strategy_name": "breakout",
                    "timeframe": "1d",
                    "rank": 2,
                    "score": 1.08,
                    "degradation": 0.18,
                    "symbols_covered": 18,
                    "evidence": {"best_window": 30},
                },
            ],
        }

        root_response = self.client.get("/v1/admin/backtests")
        self.assertEqual(root_response.status_code, 200)
        self.assertEqual(root_response.json()["areas"], ["runs", "rankings"])

        list_response = self.client.get(
            "/v1/admin/backtests/runs",
            params={"status": "completed", "timeframe": "1d", "limit": 25, "offset": 0},
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(
            list_response.json(),
            {
                "data": [
                    {
                        "id": 12,
                        "strategy_name": "ranking_refresh",
                        "symbol": "*",
                        "timeframe": "1d",
                        "window_days": 365,
                        "status": "completed",
                        "summary": {"ranking_count": 2, "top_strategy": "trend_following"},
                        "metrics": {
                            "rankings": [
                                {"strategy_name": "trend_following", "score": 1.42},
                                {"strategy_name": "breakout", "score": 1.08},
                            ]
                        },
                        "evidence": {"strategies": ["trend_following", "breakout"]},
                        "error_message": None,
                        "started_at": "2026-04-04T23:30:00Z",
                        "completed_at": "2026-04-04T23:32:00Z",
                    }
                ],
                "total": 1,
                "limit": 25,
                "offset": 0,
                "has_more": False,
            },
        )

        detail_response = self.client.get("/v1/admin/backtests/runs/12")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["id"], 12)
        self.assertEqual(
            detail_response.json()["metrics"]["rankings"][0]["strategy_name"], "trend_following"
        )

        rankings_response = self.client.get(
            "/v1/admin/backtests/rankings/latest",
            params={"timeframe": "1d", "limit": 10},
        )
        self.assertEqual(rankings_response.status_code, 200)
        self.assertEqual(
            rankings_response.json(),
            {
                "as_of_date": "2026-04-05T00:00:00Z",
                "data": [
                    {
                        "id": 101,
                        "strategy_name": "trend_following",
                        "timeframe": "1d",
                        "rank": 1,
                        "score": 1.42,
                        "degradation": 0.11,
                        "symbols_covered": 18,
                        "evidence": {"best_window": 90},
                        "as_of_date": "2026-04-05T00:00:00Z",
                    },
                    {
                        "id": 102,
                        "strategy_name": "breakout",
                        "timeframe": "1d",
                        "rank": 2,
                        "score": 1.08,
                        "degradation": 0.18,
                        "symbols_covered": 18,
                        "evidence": {"best_window": 30},
                        "as_of_date": "2026-04-05T00:00:00Z",
                    },
                ],
                "limit": 10,
            },
        )

        create_response = self.client.post(
            "/v1/admin/backtests/runs",
            json={
                "symbols": ["AAPL", "MSFT"],
                "strategy_names": ["trend_following", "breakout"],
                "windows": [30, 90],
                "timeframe": "1d",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(create_response.json()["run_id"], 18)
        self.assertEqual(create_response.json()["ranking_count"], 2)
        self.assertEqual(
            FakeBacktestService.calls,
            [
                {
                    "symbols": ["AAPL", "MSFT"],
                    "strategy_names": ["trend_following", "breakout"],
                    "windows": [30, 90],
                    "timeframe": "1d",
                }
            ],
        )

    def test_scanner_routes_observability_and_live_decisions(self) -> None:
        now = datetime(2026, 4, 5, tzinfo=timezone.utc)
        completed_run = SimpleNamespace(
            id=7,
            bucket_id=3,
            status="completed",
            scanned_count=12,
            emitted_count=4,
            suppressed_count=3,
            started_at=now - timedelta(minutes=15),
            finished_at=now - timedelta(minutes=13),
            error_message=None,
        )
        failed_run = SimpleNamespace(
            id=8,
            bucket_id=3,
            status="failed",
            scanned_count=5,
            emitted_count=1,
            suppressed_count=0,
            started_at=now - timedelta(minutes=10),
            finished_at=now - timedelta(minutes=9),
            error_message="provider_timeout",
        )
        decision_emitted = SimpleNamespace(
            id=501,
            run_id=7,
            symbol="AAPL",
            decision="emitted",
            reason="signal_generated",
            signal_type="buy",
            score=88.0,
            suppressed=False,
            dedupe_key="AAPL:buy:trend",
            created_at=now - timedelta(minutes=14),
        )
        decision_suppressed = SimpleNamespace(
            id=502,
            run_id=7,
            symbol="MSFT",
            decision="suppressed",
            reason="cooldown_active",
            signal_type="buy",
            score=71.0,
            suppressed=True,
            dedupe_key="MSFT:buy:trend",
            created_at=now - timedelta(minutes=14),
        )
        decision_error = SimpleNamespace(
            id=503,
            run_id=8,
            symbol="NVDA",
            decision="error",
            reason="RuntimeError: provider timeout",
            signal_type=None,
            score=None,
            suppressed=False,
            dedupe_key=None,
            created_at=now - timedelta(minutes=9),
        )

        FakeScannerRunRepository.runs = [completed_run, failed_run]
        FakeScannerRunRepository.runs_by_id = {7: completed_run, 8: failed_run}
        FakeScannerRunRepository.decisions = [decision_emitted, decision_suppressed, decision_error]

        root_response = self.client.get("/v1/admin/scanner")
        self.assertEqual(root_response.status_code, 200)
        self.assertEqual(root_response.json()["areas"], ["observability", "live-decision"])

        observability_response = self.client.get(
            "/v1/admin/scanner/observability",
            params={"bucket_id": 3, "limit": 10, "offset": 0, "decision_limit": 5},
        )
        self.assertEqual(observability_response.status_code, 200)
        self.assertEqual(
            observability_response.json(),
            {
                "summary": {
                    "total_runs": 2,
                    "running_runs": 0,
                    "completed_runs": 1,
                    "failed_runs": 1,
                    "total_decisions": 3,
                    "emitted_decisions": 1,
                    "suppressed_decisions": 1,
                    "skipped_decisions": 0,
                    "error_decisions": 1,
                },
                "runs": [
                    {
                        "id": 7,
                        "bucket_id": 3,
                        "status": "completed",
                        "scanned_count": 12,
                        "emitted_count": 4,
                        "suppressed_count": 3,
                        "started_at": "2026-04-04T23:45:00Z",
                        "finished_at": "2026-04-04T23:47:00Z",
                        "error_message": None,
                        "duration_seconds": 120.0,
                    },
                    {
                        "id": 8,
                        "bucket_id": 3,
                        "status": "failed",
                        "scanned_count": 5,
                        "emitted_count": 1,
                        "suppressed_count": 0,
                        "started_at": "2026-04-04T23:50:00Z",
                        "finished_at": "2026-04-04T23:51:00Z",
                        "error_message": "provider_timeout",
                        "duration_seconds": 60.0,
                    },
                ],
                "runs_total": 2,
                "limit": 10,
                "offset": 0,
                "has_more": False,
                "recent_decisions": [
                    {
                        "id": 501,
                        "run_id": 7,
                        "symbol": "AAPL",
                        "decision": "emitted",
                        "reason": "signal_generated",
                        "signal_type": "buy",
                        "score": 88.0,
                        "suppressed": False,
                        "dedupe_key": "AAPL:buy:trend",
                        "created_at": "2026-04-04T23:46:00Z",
                    },
                    {
                        "id": 502,
                        "run_id": 7,
                        "symbol": "MSFT",
                        "decision": "suppressed",
                        "reason": "cooldown_active",
                        "signal_type": "buy",
                        "score": 71.0,
                        "suppressed": True,
                        "dedupe_key": "MSFT:buy:trend",
                        "created_at": "2026-04-04T23:46:00Z",
                    },
                    {
                        "id": 503,
                        "run_id": 8,
                        "symbol": "NVDA",
                        "decision": "error",
                        "reason": "RuntimeError: provider timeout",
                        "signal_type": None,
                        "score": None,
                        "suppressed": False,
                        "dedupe_key": None,
                        "created_at": "2026-04-04T23:51:00Z",
                    },
                ],
                "decision_limit": 5,
            },
        )

        detail_response = self.client.get(
            "/v1/admin/scanner/runs/7",
            params={"decision_limit": 20},
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["run"]["id"], 7)
        self.assertEqual(len(detail_response.json()["decisions"]), 2)

        live_decision_response = self.client.get(
            "/v1/admin/scanner/live-decision",
            params={"decision": "suppressed", "suppressed": True, "limit": 10, "offset": 0},
        )
        self.assertEqual(live_decision_response.status_code, 200)
        self.assertEqual(
            live_decision_response.json(),
            {
                "data": [
                    {
                        "id": 502,
                        "run_id": 7,
                        "symbol": "MSFT",
                        "decision": "suppressed",
                        "reason": "cooldown_active",
                        "signal_type": "buy",
                        "score": 71.0,
                        "suppressed": True,
                        "dedupe_key": "MSFT:buy:trend",
                        "created_at": "2026-04-04T23:46:00Z",
                    }
                ],
                "total": 1,
                "limit": 10,
                "offset": 0,
                "has_more": False,
            },
        )
