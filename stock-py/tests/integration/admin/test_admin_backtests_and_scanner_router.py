from __future__ import annotations

import json
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.admin_api.dependencies import get_analytics_repository
from apps.admin_api.routers import backtests as backtests_router
from apps.admin_api.routers import scanner as scanner_router
from domains.signals.calibration_service import CalibrationService
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
    def _filter_runs(
        cls,
        *,
        status=None,
        strategy_name=None,
        experiment_name=None,
        run_key=None,
        timeframe=None,
        symbol=None,
    ):
        items = list(cls.runs)
        if status:
            items = [item for item in items if str(getattr(item, "status", "")) == status]
        if strategy_name:
            items = [item for item in items if item.strategy_name == strategy_name]
        if experiment_name:
            items = [item for item in items if getattr(item, "experiment_name", None) == experiment_name]
        if run_key:
            items = [item for item in items if getattr(item, "run_key", None) == run_key]
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
            experiment_name=kwargs.get("experiment_name"),
            run_key=kwargs.get("run_key"),
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
                experiment_name=kwargs.get("experiment_name"),
                run_key=kwargs.get("run_key"),
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
    window_calls = []
    return_value = {}
    window_result = None

    def __init__(self, db) -> None:
        self.db = db

    @classmethod
    def reset(cls) -> None:
        cls.calls = []
        cls.window_calls = []
        cls.return_value = {}
        cls.window_result = None

    async def refresh_rankings(
        self,
        *,
        symbols=None,
        strategy_names=None,
        windows=None,
        timeframe="1d",
        experiment_name=None,
        experiment_context=None,
        artifact_entries=None,
    ):
        self.calls.append(
            {
                "symbols": list(symbols) if symbols is not None else None,
                "strategy_names": list(strategy_names) if strategy_names is not None else None,
                "windows": list(windows) if windows is not None else None,
                "timeframe": timeframe,
                "experiment_name": experiment_name,
                "experiment_context": deepcopy(experiment_context),
                "artifact_entries": deepcopy(artifact_entries),
            }
        )
        return deepcopy(self.return_value)

    async def run_backtest_window(
        self,
        *,
        symbol,
        window_days,
        strategy_name,
        timeframe="1d",
    ):
        self.window_calls.append(
            {
                "symbol": symbol,
                "window_days": window_days,
                "strategy_name": strategy_name,
                "timeframe": timeframe,
            }
        )
        return deepcopy(self.window_result)


class FakeAnalyticsRepository:
    calls: dict[str, list[int]] = {}

    @classmethod
    def reset(cls) -> None:
        cls.calls = {"query_strategy_health": [], "query_signal_results": []}

    async def query_strategy_health(self, window_hours: int = 24 * 7):
        self.calls["query_strategy_health"].append(window_hours)
        refreshed_at = datetime(2026, 4, 5, 7, 0, tzinfo=timezone.utc)
        return {
            "window_hours": window_hours,
            "strategies": [
                {
                    "strategy_name": "trend_following",
                    "rank": 1,
                    "score": 1.18,
                    "degradation": 1.4,
                    "signals_generated": 22,
                    "stable": True,
                },
                {
                    "strategy_name": "breakout",
                    "rank": 2,
                    "score": 1.05,
                    "degradation": 3.2,
                    "signals_generated": 14,
                    "stable": True,
                },
                {
                    "strategy_name": "mean_reversion",
                    "rank": 4,
                    "score": 0.83,
                    "degradation": 11.2,
                    "signals_generated": 6,
                    "stable": False,
                },
            ],
            "refreshed_at": refreshed_at,
        }

    async def query_signal_results(self, window_hours: int = 24):
        self.calls["query_signal_results"].append(window_hours)
        generated_after = datetime(2026, 4, 3, 8, 0, tzinfo=timezone.utc)
        return {
            "window_hours": window_hours,
            "generated_after": generated_after,
            "total_signals": 42,
            "total_trade_actions": 14,
            "trade_action_rate": 33.3333,
            "executed_trade_rate": 19.0476,
            "overlapping_symbols": 8,
            "signal_strategies": [
                {"key": "trend_following", "count": 21},
                {"key": "breakout", "count": 13},
                {"key": "mean_reversion", "count": 5},
                {"key": "range_rotation", "count": 3},
            ],
            "market_regimes": [
                {"key": "trend_up", "count": 28},
                {"key": "range_balanced", "count": 14},
            ],
        }


class FakeSignalCalibrationSnapshotRepository:
    calls: dict[str, list[dict]] = {}
    calibration_service = CalibrationService()
    active_snapshot: dict | None = None

    def __init__(self, db) -> None:
        self.db = db

    @classmethod
    def reset(cls) -> None:
        cls.calls = {"get_active_snapshot": [], "create_snapshot": []}
        cls.active_snapshot = {
            "id": 2,
            "version": "signals-v2-review-20260410",
            "source": "manual_review",
            "strategy_weights": dict(cls.calibration_service.DEFAULT_STRATEGY_WEIGHTS),
            "score_multipliers": dict(cls.calibration_service.DEFAULT_SCORE_MULTIPLIERS),
            "atr_multipliers": dict(cls.calibration_service.DEFAULT_ATR_MULTIPLIERS),
            "is_active": True,
            "effective_from": datetime(2026, 4, 5, 6, 0, tzinfo=timezone.utc),
            "effective_at": datetime(2026, 4, 5, 6, 0, tzinfo=timezone.utc),
            "created_at": datetime(2026, 4, 5, 6, 0, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 4, 5, 6, 0, tzinfo=timezone.utc),
            "notes": "Active review snapshot.",
        }

    async def get_active_snapshot(self):
        self.calls["get_active_snapshot"].append({})
        return deepcopy(self.active_snapshot)

    async def create_snapshot(
        self,
        *,
        version,
        source="manual_review",
        strategy_weights=None,
        score_multipliers=None,
        atr_multipliers=None,
        derived_from=None,
        sample_size=None,
        activate=False,
        effective_from=None,
        effective_at=None,
        notes=None,
    ):
        self.calls["create_snapshot"].append(
            {
                "version": version,
                "source": source,
                "strategy_weights": deepcopy(strategy_weights),
                "score_multipliers": deepcopy(score_multipliers),
                "atr_multipliers": deepcopy(atr_multipliers),
                "derived_from": derived_from,
                "sample_size": sample_size,
                "activate": activate,
                "effective_from": effective_from,
                "effective_at": effective_at,
                "notes": notes,
            }
        )
        normalized = self.calibration_service.normalize_snapshot(
            {
                "version": version,
                "source": source,
                "effective_from": effective_from or effective_at,
                "strategy_weights": strategy_weights or {},
                "score_multipliers": score_multipliers or {},
                "atr_multipliers": atr_multipliers or {},
            }
        )
        snapshot = {
            "id": 3,
            "version": normalized.version,
            "source": normalized.source,
            "strategy_weights": dict(normalized.strategy_weights),
            "score_multipliers": dict(normalized.score_multipliers),
            "atr_multipliers": dict(normalized.atr_multipliers),
            "derived_from": derived_from,
            "sample_size": sample_size,
            "is_active": bool(activate),
            "effective_from": normalized.effective_from,
            "effective_at": normalized.effective_from,
            "notes": notes,
            "created_at": normalized.effective_from,
            "updated_at": normalized.effective_from,
        }
        if activate:
            self.active_snapshot = deepcopy(snapshot)
        return snapshot


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
        FakeAnalyticsRepository.reset()
        FakeSignalCalibrationSnapshotRepository.reset()

        self.app = FastAPI()
        register_exception_handlers(self.app)
        self.app.include_router(backtests_router.router)
        self.app.include_router(scanner_router.router)

        async def override_db_session():
            yield object()

        async def override_analytics_repository():
            return FakeAnalyticsRepository()

        self.app.dependency_overrides[get_db_session] = override_db_session
        self.app.dependency_overrides[get_analytics_repository] = override_analytics_repository

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
        self.calibration_repository_patch = patch.object(
            backtests_router,
            "SignalCalibrationSnapshotRepository",
            FakeSignalCalibrationSnapshotRepository,
        )
        self.scanner_repository_patch = patch.object(
            scanner_router,
            "ScannerRunRepository",
            FakeScannerRunRepository,
        )
        self.backtest_repository_patch.start()
        self.backtest_service_patch.start()
        self.calibration_repository_patch.start()
        self.scanner_repository_patch.start()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        self.backtest_repository_patch.stop()
        self.backtest_service_patch.stop()
        self.calibration_repository_patch.stop()
        self.scanner_repository_patch.stop()

    def test_backtests_routes_list_detail_and_refresh(self) -> None:
        now = datetime(2026, 4, 5, tzinfo=timezone.utc)
        run = SimpleNamespace(
            id=12,
            strategy_name="ranking_refresh",
            experiment_name="cli.backtest-benchmarks",
            run_key="cli-backtest-benchmarks:1d:20260405T000000Z",
            symbol="*",
            timeframe="1d",
            window_days=365,
            status="completed",
            summary=json.dumps({"ranking_count": 2, "top_strategy": "trend_following"}),
            config=json.dumps(
                {
                    "timeframe": "1d",
                    "windows": [30, 90],
                    "strategy_names": ["trend_following", "breakout"],
                    "universe": {"count": 2, "symbols": ["AAPL", "MSFT"]},
                }
            ),
            metrics=json.dumps(
                {
                    "rankings": [
                        {"strategy_name": "trend_following", "score": 1.42},
                        {"strategy_name": "breakout", "score": 1.08},
                    ]
                }
            ),
            evidence=json.dumps({"strategies": ["trend_following", "breakout"]}),
            artifacts=json.dumps(
                {
                    "entries": [
                        {"type": "database", "name": "backtest_run", "locator": {"id": 12}},
                        {
                            "type": "database",
                            "name": "strategy_rankings",
                            "locator": {"timeframe": "1d", "count": 2},
                        },
                    ]
                }
            ),
            code_version="main@abc123def456",
            dataset_fingerprint="fingerprint-123",
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
            "experiment_name": "admin.manual-refresh",
            "run_key": "admin-manual-refresh:1d:20260405T000000Z",
            "code_version": "main@abc123def456",
            "dataset_fingerprint": "fingerprint-123",
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
        self.assertEqual(root_response.json()["areas"], ["runs", "rankings", "equity-curve"])

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
                        "experiment_name": "cli.backtest-benchmarks",
                        "run_key": "cli-backtest-benchmarks:1d:20260405T000000Z",
                        "symbol": "*",
                        "timeframe": "1d",
                        "window_days": 365,
                        "status": "completed",
                        "summary": {"ranking_count": 2, "top_strategy": "trend_following"},
                        "config": {
                            "timeframe": "1d",
                            "windows": [30, 90],
                            "strategy_names": ["trend_following", "breakout"],
                            "universe": {"count": 2, "symbols": ["AAPL", "MSFT"]},
                        },
                        "metrics": {
                            "rankings": [
                                {"strategy_name": "trend_following", "score": 1.42},
                                {"strategy_name": "breakout", "score": 1.08},
                            ]
                        },
                        "evidence": {"strategies": ["trend_following", "breakout"]},
                        "artifacts": {
                            "entries": [
                                {"type": "database", "name": "backtest_run", "locator": {"id": 12}},
                                {
                                    "type": "database",
                                    "name": "strategy_rankings",
                                    "locator": {"timeframe": "1d", "count": 2},
                                },
                            ]
                        },
                        "code_version": "main@abc123def456",
                        "dataset_fingerprint": "fingerprint-123",
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
                "experiment_name": "admin.manual-refresh",
                "auto_feedback_loop": False,
            },
        )
        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(create_response.json()["run_id"], 18)
        self.assertEqual(create_response.json()["experiment_name"], "admin.manual-refresh")
        self.assertEqual(
            create_response.json()["run_key"],
            "admin-manual-refresh:1d:20260405T000000Z",
        )
        self.assertEqual(create_response.json()["code_version"], "main@abc123def456")
        self.assertEqual(create_response.json()["dataset_fingerprint"], "fingerprint-123")
        self.assertEqual(create_response.json()["ranking_count"], 2)
        self.assertEqual(
            FakeBacktestService.calls,
            [
                {
                    "symbols": ["AAPL", "MSFT"],
                    "strategy_names": ["trend_following", "breakout"],
                    "windows": [30, 90],
                    "timeframe": "1d",
                    "experiment_name": "admin.manual-refresh",
                    "experiment_context": {
                        "trigger": "admin_api",
                        "entrypoint": "apps.admin_api.routers.backtests.create_run",
                        "dataset": {"selection_mode": "request"},
                    },
                    "artifact_entries": None,
                }
            ],
        )

    def test_backtest_equity_curve_route_returns_series(self) -> None:
        FakeBacktestService.window_result = {
            "symbol": "AAPL",
            "strategy_name": "trend_following",
            "timeframe": "1d",
            "window_days": 90,
            "metrics": {
                "total_return_percent": 14.2,
                "max_drawdown_percent": 3.8,
                "trade_count": 3,
                "win_rate": 66.6667,
                "avg_trade_return_percent": 4.1,
                "sharpe_ratio": 1.2,
                "samples": 90,
            },
            "trades": [
                {
                    "entry_index": 20,
                    "exit_index": 32,
                    "entry_price": 101.2,
                    "exit_price": 107.8,
                    "return_percent": 6.5217,
                }
            ],
            "equity_points": [1.0, 1.04, 1.09, 1.142],
            "equity_series": [
                {
                    "timestamp": "2026-04-10T00:00:00Z",
                    "equity": 1.0,
                    "drawdown_percent": 0.0,
                },
                {
                    "timestamp": "2026-04-11T00:00:00Z",
                    "equity": 1.04,
                    "drawdown_percent": 0.0,
                },
                {
                    "timestamp": "2026-04-12T00:00:00Z",
                    "equity": 1.09,
                    "drawdown_percent": 0.0,
                },
            ],
        }

        response = self.client.get(
            "/v1/admin/backtests/equity-curve",
            params={
                "symbol": "AAPL",
                "strategy_name": "trend_following",
                "window_days": 90,
                "timeframe": "1d",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "symbol": "AAPL",
                "strategy_name": "trend_following",
                "timeframe": "1d",
                "window_days": 90,
                "metrics": {
                    "total_return_percent": 14.2,
                    "max_drawdown_percent": 3.8,
                    "trade_count": 3,
                    "win_rate": 66.6667,
                    "avg_trade_return_percent": 4.1,
                    "sharpe_ratio": 1.2,
                    "samples": 90,
                },
                "trades": [
                    {
                        "entry_index": 20,
                        "exit_index": 32,
                        "entry_price": 101.2,
                        "exit_price": 107.8,
                        "return_percent": 6.5217,
                    }
                ],
                "equity_points": [1.0, 1.04, 1.09, 1.142],
                "equity_series": [
                    {
                        "timestamp": "2026-04-10T00:00:00Z",
                        "equity": 1.0,
                        "drawdown_percent": 0.0,
                    },
                    {
                        "timestamp": "2026-04-11T00:00:00Z",
                        "equity": 1.04,
                        "drawdown_percent": 0.0,
                    },
                    {
                        "timestamp": "2026-04-12T00:00:00Z",
                        "equity": 1.09,
                        "drawdown_percent": 0.0,
                    },
                ],
            },
        )
        self.assertEqual(
            FakeBacktestService.window_calls,
            [
                {
                    "symbol": "AAPL",
                    "window_days": 90,
                    "strategy_name": "trend_following",
                    "timeframe": "1d",
                }
            ],
        )

    def test_create_run_can_return_calibration_feedback_snapshot(self) -> None:
        FakeBacktestService.return_value = {
            "run_id": 24,
            "experiment_name": "admin.manual-refresh",
            "run_key": "admin-manual-refresh:1d:20260405T010000Z",
            "code_version": "main@abc123def456",
            "dataset_fingerprint": "fingerprint-456",
            "ranking_count": 1,
            "rankings": [
                {
                    "strategy_name": "trend_following",
                    "timeframe": "1d",
                    "rank": 1,
                    "score": 1.51,
                    "degradation": 0.09,
                    "symbols_covered": 20,
                    "evidence": {"best_window": 90},
                }
            ],
        }

        response = self.client.post(
            "/v1/admin/backtests/runs",
            json={
                "symbols": ["AAPL"],
                "strategy_names": ["trend_following"],
                "timeframe": "1d",
                "experiment_name": "admin.manual-refresh",
                "activate_feedback_snapshot": False,
                "feedback_signal_window_hours": 48,
                "feedback_ranking_window_hours": 336,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["run_id"], 24)
        self.assertEqual(payload["calibration_feedback"]["previous_version"], "signals-v2-review-20260410")
        self.assertFalse(payload["calibration_feedback"]["activated"])
        self.assertTrue(payload["calibration_feedback"]["applied_version"].startswith("signals-v2-feedback-"))
        self.assertGreater(payload["calibration_feedback"]["strategy_weights"]["trend_continuation"], 1.0)
        self.assertGreater(payload["calibration_feedback"]["atr_multipliers"]["trend"], 2.2)
        self.assertEqual(FakeAnalyticsRepository.calls["query_signal_results"], [48])
        self.assertEqual(FakeAnalyticsRepository.calls["query_strategy_health"], [336])
        self.assertEqual(len(FakeSignalCalibrationSnapshotRepository.calls["create_snapshot"]), 1)
        self.assertFalse(FakeSignalCalibrationSnapshotRepository.calls["create_snapshot"][0]["activate"])

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
