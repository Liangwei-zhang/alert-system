from __future__ import annotations

import json
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.public_api.routers import strategy_breakdown
from infra.core.errors import register_exception_handlers
from infra.db.session import get_db_session


class FakeSignalRepository:
    signals: dict[int, SimpleNamespace] = {}

    def __init__(self, db) -> None:
        self.db = db

    @classmethod
    def reset(cls) -> None:
        generated_at = datetime(2026, 4, 12, 9, 30, tzinfo=timezone.utc)
        cls.signals = {
            11: SimpleNamespace(
                id=11,
                symbol="AAPL",
                signal_type="buy",
                generated_at=generated_at,
                indicators=json.dumps(
                    {
                        "strategy_window": "1d",
                        "market_regime": "trend",
                        "market_regime_detail": "trend_strong_up",
                        "regime_duration_bars": 15,
                        "regime_metrics": {"trend_strength": 0.92, "momentum_score": 0.88},
                        "regime_reasons": ["strong-trend-threshold"],
                        "calibration_version": "signals-v2-feedback-20260412T093000Z-r24",
                        "calibration_snapshot": {
                            "version": "signals-v2-feedback-20260412T093000Z-r24",
                            "source": "backtest_feedback_loop",
                            "effective_from": "2026-04-12T09:30:00Z",
                        },
                        "strategy_selection": {
                            "strategy": "trend_continuation",
                            "source": "ranking",
                            "source_strategy": "trend_following",
                            "rank": 1,
                            "ranking_score": 18.0,
                            "combined_score": 23.4,
                            "signal_fit_score": 7.9,
                            "regime_bias": 3.0,
                            "degradation_penalty": 0.2,
                            "stable": True,
                            "market_regime_detail": "trend_strong_up",
                            "regime_duration_bars": 15,
                            "strategy_weight": 1.08,
                            "calibration_version": "signals-v2-feedback-20260412T093000Z-r24",
                        },
                        "strategy_candidates": [
                            {
                                "strategy": "trend_continuation",
                                "source": "ranking",
                                "source_strategy": "trend_following",
                                "rank": 1,
                                "ranking_score": 18.0,
                                "combined_score": 23.4,
                                "signal_fit_score": 7.9,
                                "regime_bias": 3.0,
                                "degradation_penalty": 0.2,
                                "stable": True,
                                "market_regime_detail": "trend_strong_up",
                                "regime_duration_bars": 15,
                                "strategy_weight": 1.08,
                                "calibration_version": "signals-v2-feedback-20260412T093000Z-r24",
                            },
                            {
                                "strategy": "volatility_breakout",
                                "source": "ranking",
                                "source_strategy": "breakout",
                                "rank": 2,
                                "ranking_score": 13.5,
                                "combined_score": 16.8,
                                "signal_fit_score": 6.1,
                                "regime_bias": 0.5,
                                "degradation_penalty": 1.5,
                                "stable": True,
                                "market_regime_detail": "trend_strong_up",
                                "regime_duration_bars": 15,
                                "strategy_weight": 1.0,
                                "calibration_version": "signals-v2-feedback-20260412T093000Z-r24",
                            },
                        ],
                        "alert_decision": {
                            "publish_allowed": True,
                            "suppressed_reasons": [],
                        },
                    }
                ),
            )
        }

    async def get_signal(self, signal_id: int):
        signal = self.signals.get(int(signal_id))
        return deepcopy(signal) if signal is not None else None

    @staticmethod
    def _load_metadata(signal) -> dict:
        if not getattr(signal, "indicators", None):
            return {}
        return json.loads(signal.indicators)


class StrategyBreakdownRouterIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        FakeSignalRepository.reset()

        self.app = FastAPI()
        register_exception_handlers(self.app)
        self.app.include_router(strategy_breakdown.router, prefix="/v1")

        async def override_db_session():
            yield object()

        self.app.dependency_overrides[get_db_session] = override_db_session
        self.repository_patch = patch.object(
            strategy_breakdown,
            "SignalRepository",
            FakeSignalRepository,
        )
        self.repository_patch.start()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        self.repository_patch.stop()

    def test_strategy_breakdown_route_returns_selection_and_candidates(self) -> None:
        response = self.client.get("/v1/signals/11/strategy-breakdown")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["signal_id"], 11)
        self.assertEqual(payload["symbol"], "AAPL")
        self.assertEqual(payload["selected_strategy"], "trend_continuation")
        self.assertEqual(payload["selection_source"], "ranking")
        self.assertEqual(payload["market_regime_detail"], "trend_strong_up")
        self.assertEqual(payload["regime_duration_bars"], 15)
        self.assertEqual(payload["calibration_source"], "backtest_feedback_loop")
        self.assertEqual(payload["calibration_effective_from"], "2026-04-12T09:30:00Z")
        self.assertEqual(payload["selected_candidate"]["strategy_weight"], 1.08)
        self.assertEqual(len(payload["candidates"]), 2)
        self.assertEqual(payload["candidates"][1]["strategy"], "volatility_breakout")
        self.assertEqual(payload["alert_decision"]["publish_allowed"], True)

    def test_strategy_breakdown_route_returns_not_found(self) -> None:
        response = self.client.get("/v1/signals/999/strategy-breakdown")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "signal_not_found")


if __name__ == "__main__":
    unittest.main()