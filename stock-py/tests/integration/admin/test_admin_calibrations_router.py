from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.admin_api.dependencies import get_analytics_repository
from apps.admin_api.routers import calibrations as calibrations_router
from domains.signals.calibration_service import CalibrationService
from infra.core.errors import register_exception_handlers
from infra.db.session import get_db_session


class FakeSignalCalibrationSnapshotRepository:
    snapshots: list[dict] = []
    calls: dict[str, list] = {}
    calibration_service = CalibrationService()

    def __init__(self, db) -> None:
        self.db = db

    @classmethod
    def reset(cls) -> None:
        created_at = datetime(2026, 4, 11, 7, 15, tzinfo=timezone.utc)
        cls.snapshots = [
            {
                "id": 1,
                "version": "signals-v2-default",
                "source": "default",
                "strategy_weights": dict(cls.calibration_service.DEFAULT_STRATEGY_WEIGHTS),
                "score_multipliers": dict(cls.calibration_service.DEFAULT_SCORE_MULTIPLIERS),
                "atr_multipliers": dict(cls.calibration_service.DEFAULT_ATR_MULTIPLIERS),
                "derived_from": "bootstrap",
                "sample_size": None,
                "is_active": False,
                "effective_from": None,
                "effective_at": None,
                "notes": "Bootstrap fallback snapshot.",
                "created_at": created_at,
                "updated_at": created_at,
            },
            {
                "id": 2,
                "version": "signals-v2-review-20260411",
                "source": "manual_review",
                "strategy_weights": {
                    **dict(cls.calibration_service.DEFAULT_STRATEGY_WEIGHTS),
                    "trend_continuation": 1.12,
                },
                "score_multipliers": {
                    **dict(cls.calibration_service.DEFAULT_SCORE_MULTIPLIERS),
                    "confidence": 1.08,
                },
                "atr_multipliers": {
                    **dict(cls.calibration_service.DEFAULT_ATR_MULTIPLIERS),
                    "trend_up": 2.35,
                },
                "derived_from": "backtest:30d-ranking + live:24h-results",
                "sample_size": 128,
                "is_active": True,
                "effective_from": created_at,
                "effective_at": created_at,
                "notes": "Reviewed and activated after morning calibration pass.",
                "created_at": created_at,
                "updated_at": created_at,
            },
        ]
        cls.calls = {
            "list_snapshots": [],
            "count_snapshots": [],
            "get_active_snapshot": [],
            "create_snapshot": [],
        }

    async def list_snapshots(self, *, limit=20, offset=0, active_only=False):
        self.calls["list_snapshots"].append(
            {"limit": limit, "offset": offset, "active_only": active_only}
        )
        items = list(self.snapshots)
        if active_only:
            items = [item for item in items if item["is_active"]]
        items = sorted(
            items,
            key=lambda item: (
                int(bool(item["is_active"])),
                item["effective_from"] or item["effective_at"] or item["created_at"],
                item["id"],
            ),
            reverse=True,
        )
        return deepcopy(items[offset : offset + limit])

    async def count_snapshots(self, *, active_only=False):
        self.calls["count_snapshots"].append({"active_only": active_only})
        if not active_only:
            return len(self.snapshots)
        return len([item for item in self.snapshots if item["is_active"]])

    async def get_active_snapshot(self):
        self.calls["get_active_snapshot"].append({})
        for item in self.snapshots:
            if item["is_active"]:
                return deepcopy(item)
        return None

    async def activate_snapshot(self, snapshot_id: int):
        snapshot_id = int(snapshot_id)
        target = None
        for item in self.snapshots:
            if item["id"] == snapshot_id:
                target = item
                break
        if target is None:
            raise ValueError("Calibration snapshot not found")
        effective_at = datetime(2026, 4, 11, 9, 0, tzinfo=timezone.utc)
        for item in self.snapshots:
            item["is_active"] = False
        target["is_active"] = True
        target["effective_from"] = effective_at
        target["effective_at"] = effective_at
        target["updated_at"] = effective_at
        return deepcopy(target)

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
                "strategy_weights": strategy_weights,
                "score_multipliers": score_multipliers,
                "atr_multipliers": atr_multipliers,
                "derived_from": derived_from,
                "sample_size": sample_size,
                "activate": activate,
                "effective_from": effective_from,
                "effective_at": effective_at,
                "notes": notes,
            }
        )
        if any(item["version"] == version for item in self.snapshots):
            raise ValueError(f"Calibration snapshot version '{version}' already exists")

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
        applied_effective_from = normalized.effective_from or (
            datetime(2026, 4, 11, 8, 0, tzinfo=timezone.utc) if activate else None
        )
        now = applied_effective_from or datetime(2026, 4, 11, 8, 0, tzinfo=timezone.utc)
        if activate:
            for item in self.snapshots:
                item["is_active"] = False
        snapshot = {
            "id": max(item["id"] for item in self.snapshots) + 1,
            "version": normalized.version,
            "source": normalized.source,
            "strategy_weights": dict(normalized.strategy_weights),
            "score_multipliers": dict(normalized.score_multipliers),
            "atr_multipliers": dict(normalized.atr_multipliers),
            "derived_from": derived_from,
            "sample_size": sample_size,
            "is_active": bool(activate),
            "effective_from": applied_effective_from,
            "effective_at": applied_effective_from,
            "notes": notes,
            "created_at": now,
            "updated_at": now,
        }
        self.snapshots.append(snapshot)
        return deepcopy(snapshot)


class FakeAnalyticsRepository:
    async def query_strategy_health(self, window_hours: int = 24 * 7):
        refreshed_at = datetime(2026, 4, 11, 7, 0, tzinfo=timezone.utc)
        return {
            "window_hours": window_hours,
            "strategies": [
                {
                    "strategy_name": "momentum",
                    "rank": 1,
                    "score": 1.16,
                    "degradation": 2.1,
                    "signals_generated": 19,
                    "stable": True,
                },
                {
                    "strategy_name": "breakout",
                    "rank": 2,
                    "score": 1.04,
                    "degradation": 3.0,
                    "signals_generated": 12,
                    "stable": True,
                },
                {
                    "strategy_name": "mean_reversion",
                    "rank": 4,
                    "score": 0.84,
                    "degradation": 12.0,
                    "signals_generated": 5,
                    "stable": False,
                },
            ],
            "refreshed_at": refreshed_at,
        }

    async def query_signal_results(self, window_hours: int = 24):
        generated_after = datetime(2026, 4, 10, 8, 0, tzinfo=timezone.utc)
        return {
            "window_hours": window_hours,
            "generated_after": generated_after,
            "total_signals": 48,
            "total_trade_actions": 14,
            "trade_action_rate": 29.1667,
            "executed_trade_rate": 18.75,
            "overlapping_symbols": 8,
            "signal_strategies": [
                {"key": "momentum", "count": 24},
                {"key": "breakout", "count": 13},
                {"key": "mean_reversion", "count": 7},
                {"key": "range_rotation", "count": 4},
            ],
            "market_regimes": [
                {"key": "trend_up", "count": 28},
                {"key": "range", "count": 14},
            ],
        }


class AdminCalibrationsRouterIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        FakeSignalCalibrationSnapshotRepository.reset()

        self.app = FastAPI()
        register_exception_handlers(self.app)
        self.app.include_router(calibrations_router.router)

        async def override_db_session():
            yield object()

        async def override_analytics_repository():
            return FakeAnalyticsRepository()

        self.app.dependency_overrides[get_db_session] = override_db_session
        self.app.dependency_overrides[get_analytics_repository] = override_analytics_repository

        self.repository_patch = patch.object(
            calibrations_router,
            "SignalCalibrationSnapshotRepository",
            FakeSignalCalibrationSnapshotRepository,
        )
        self.repository_patch.start()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        self.repository_patch.stop()

    def test_list_and_active_routes_expose_snapshot_history(self) -> None:
        response = self.client.get("/v1/admin/calibrations", params={"limit": 10})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 2)
        self.assertFalse(payload["has_more"])
        self.assertEqual(payload["data"][0]["version"], "signals-v2-review-20260411")
        self.assertTrue(payload["data"][0]["is_active"])
        self.assertEqual(payload["data"][0]["effective_from"], "2026-04-11T07:15:00Z")
        self.assertEqual(payload["data"][0]["atr_multipliers"]["trend_up"], 2.35)
        self.assertEqual(payload["data"][1]["version"], "signals-v2-default")

        active = self.client.get("/v1/admin/calibrations/active")
        self.assertEqual(active.status_code, 200)
        active_payload = active.json()
        self.assertEqual(active_payload["data"]["version"], "signals-v2-review-20260411")
        self.assertEqual(active_payload["data"]["source"], "manual_review")
        self.assertEqual(active_payload["data"]["effective_from"], "2026-04-11T07:15:00Z")

    def test_create_route_normalizes_and_activates_snapshot(self) -> None:
        response = self.client.post(
            "/v1/admin/calibrations",
            json={
                "version": "signals-v2-review-20260412",
                "source": "manual_review",
                "activate": True,
                "derived_from": "backtest:7d-ranking + live:24h-results",
                "sample_size": 96,
                "strategy_weights": {"mean_reversion": 1.8},
                "score_multipliers": {"liquidity_penalty": 0.2},
                "atr_multipliers": {"trend_strong_up": 4.8},
                "effective_from": "2026-04-11T10:15:00Z",
                "notes": "Activate reviewed canary snapshot.",
            },
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["version"], "signals-v2-review-20260412")
        self.assertTrue(payload["is_active"])
        self.assertEqual(payload["strategy_weights"]["mean_reversion"], 1.25)
        self.assertEqual(payload["score_multipliers"]["liquidity_penalty"], 0.75)
        self.assertEqual(payload["atr_multipliers"]["trend_strong_up"], 4.0)
        self.assertEqual(payload["effective_from"], "2026-04-11T10:15:00Z")

        active = self.client.get("/v1/admin/calibrations/active")
        self.assertEqual(active.status_code, 200)
        self.assertEqual(active.json()["data"]["version"], "signals-v2-review-20260412")

    def test_create_route_returns_conflict_for_duplicate_version(self) -> None:
        response = self.client.post(
            "/v1/admin/calibrations",
            json={
                "version": "signals-v2-default",
                "source": "manual_review",
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["error"]["code"],
            "calibration_snapshot_conflict",
        )
        self.assertIn("already exists", response.json()["error"]["message"])

    def test_proposal_route_returns_reviewable_recommendations(self) -> None:
        response = self.client.get(
            "/v1/admin/calibrations/proposal",
            params={"signal_window_hours": 24, "ranking_window_hours": 168},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["current_version"], "signals-v2-review-20260411")
        self.assertEqual(payload["summary"]["total_signals"], 48)
        self.assertEqual(payload["summary"]["active_calibration_version"], "signals-v2-review-20260411")
        self.assertTrue(payload["proposed_version"].startswith("signals-v2-proposal-"))
        self.assertEqual(payload["snapshot_payload"]["source"], "proposal")
        self.assertIsNotNone(payload["snapshot_payload"]["effective_from"])

        strategy_weights = {item["key"]: item for item in payload["strategy_weights"]}
        self.assertGreater(
            strategy_weights["trend_continuation"]["proposed_value"],
            strategy_weights["trend_continuation"]["current_value"],
        )
        self.assertLess(
            strategy_weights["mean_reversion"]["proposed_value"],
            strategy_weights["mean_reversion"]["current_value"],
        )

        score_multipliers = {item["key"]: item for item in payload["score_multipliers"]}
        self.assertGreater(score_multipliers["trend"]["proposed_value"], 1.0)
        self.assertGreater(score_multipliers["stale_penalty"]["proposed_value"], 1.0)

        atr_multipliers = {item["key"]: item for item in payload["atr_multipliers"]}
        self.assertGreater(
            atr_multipliers["trend"]["proposed_value"],
            atr_multipliers["trend"]["current_value"],
        )

    def test_activate_route_switches_active_snapshot(self) -> None:
        response = self.client.post("/v1/admin/calibrations/1/activate")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], 1)
        self.assertTrue(payload["is_active"])
        self.assertEqual(payload["effective_from"], "2026-04-11T09:00:00Z")

        active = self.client.get("/v1/admin/calibrations/active")
        self.assertEqual(active.status_code, 200)
        self.assertEqual(active.json()["data"]["id"], 1)

    def test_activate_route_returns_not_found_for_unknown_snapshot(self) -> None:
        response = self.client.post("/v1/admin/calibrations/999/activate")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["error"]["code"],
            "calibration_snapshot_not_found",
        )

    def test_apply_proposal_route_creates_snapshot_from_latest_recommendation(self) -> None:
        response = self.client.post(
            "/v1/admin/calibrations/proposal/apply",
            json={
                "signal_window_hours": 24,
                "ranking_window_hours": 168,
                "version": "signals-v2-proposal-20260411-r1",
                "activate": True,
                "notes": "Approved by operator review.",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["version"], "signals-v2-proposal-20260411-r1")
        self.assertEqual(payload["source"], "proposal_review")
        self.assertTrue(payload["is_active"])
        self.assertGreater(payload["strategy_weights"]["trend_continuation"], 1.0)
        self.assertIn("trend", payload["atr_multipliers"])
        self.assertIsNotNone(payload["effective_from"])

    def test_apply_proposal_route_returns_conflict_for_duplicate_version(self) -> None:
        response = self.client.post(
            "/v1/admin/calibrations/proposal/apply",
            json={
                "version": "signals-v2-default",
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["error"]["code"],
            "calibration_snapshot_conflict",
        )


if __name__ == "__main__":
    unittest.main()