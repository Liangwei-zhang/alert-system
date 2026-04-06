from __future__ import annotations

import json
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.admin_api.routers import anomalies as anomalies_router
from apps.admin_api.routers import signal_stats as signal_stats_router
from infra.core.errors import register_exception_handlers
from infra.db.session import get_db_session


class FakeSignalRepository:
    records = []
    summary_payload = {}
    calls: dict[str, list] = {}

    def __init__(self, db) -> None:
        self.db = db

    @classmethod
    def reset(cls) -> None:
        cls.records = []
        cls.summary_payload = {}
        cls.calls = {
            "list_admin_signals": [],
            "count_admin_signals": [],
            "summarize_admin_signals": [],
        }

    @classmethod
    def _filter_records(
        cls,
        *,
        status: str | None = None,
        signal_type: str | None = None,
        symbol: str | None = None,
        validation_status: str | None = None,
    ):
        items = list(cls.records)
        if status:
            items = [item for item in items if str(item.status) == status]
        if signal_type:
            items = [item for item in items if str(item.signal_type) == signal_type]
        if symbol:
            items = [item for item in items if item.symbol == symbol.upper()]
        if validation_status:
            items = [item for item in items if str(item.validation_status) == validation_status]
        return items

    async def list_admin_signals(self, **kwargs):
        self.calls["list_admin_signals"].append(kwargs)
        items = self._filter_records(
            status=kwargs.get("status"),
            signal_type=kwargs.get("signal_type"),
            symbol=kwargs.get("symbol"),
            validation_status=kwargs.get("validation_status"),
        )
        offset = int(kwargs.get("offset", 0) or 0)
        limit = int(kwargs.get("limit", len(items)) or len(items))
        return list(items[offset : offset + limit])

    async def count_admin_signals(self, **kwargs):
        self.calls["count_admin_signals"].append(kwargs)
        return len(
            self._filter_records(
                status=kwargs.get("status"),
                signal_type=kwargs.get("signal_type"),
                symbol=kwargs.get("symbol"),
                validation_status=kwargs.get("validation_status"),
            )
        )

    async def summarize_admin_signals(self, *, window_hours: int = 24 * 7):
        self.calls["summarize_admin_signals"].append({"window_hours": window_hours})
        return deepcopy(self.summary_payload)


class FakeOhlcvRepository:
    anomalies = []
    calls: dict[str, list] = {}

    def __init__(self, db) -> None:
        self.db = db

    @classmethod
    def reset(cls) -> None:
        cls.anomalies = []
        cls.calls = {
            "list_anomalies": [],
            "count_anomalies": [],
        }

    @classmethod
    def _filter_anomalies(
        cls,
        *,
        symbol: str | None = None,
        timeframe: str | None = None,
        severity: str | None = None,
        anomaly_code: str | None = None,
        source: str | None = None,
    ):
        items = list(cls.anomalies)
        if symbol:
            items = [item for item in items if item.symbol == symbol.upper()]
        if timeframe:
            items = [item for item in items if item.timeframe == timeframe]
        if severity:
            items = [item for item in items if item.severity == severity]
        if anomaly_code:
            items = [item for item in items if item.anomaly_code == anomaly_code]
        if source:
            items = [item for item in items if item.source == source]
        return items

    async def list_anomalies(self, **kwargs):
        self.calls["list_anomalies"].append(kwargs)
        items = self._filter_anomalies(
            symbol=kwargs.get("symbol"),
            timeframe=kwargs.get("timeframe"),
            severity=kwargs.get("severity"),
            anomaly_code=kwargs.get("anomaly_code"),
            source=kwargs.get("source"),
        )
        offset = int(kwargs.get("offset", 0) or 0)
        limit = int(kwargs.get("limit", len(items)) or len(items))
        return list(items[offset : offset + limit])

    async def count_anomalies(self, **kwargs):
        self.calls["count_anomalies"].append(kwargs)
        return len(
            self._filter_anomalies(
                symbol=kwargs.get("symbol"),
                timeframe=kwargs.get("timeframe"),
                severity=kwargs.get("severity"),
                anomaly_code=kwargs.get("anomaly_code"),
                source=kwargs.get("source"),
            )
        )


class AdminSignalStatsAndAnomaliesRouterIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        FakeSignalRepository.reset()
        FakeOhlcvRepository.reset()

        self.app = FastAPI()
        register_exception_handlers(self.app)
        self.app.include_router(signal_stats_router.router)
        self.app.include_router(anomalies_router.router)

        async def override_db_session():
            yield object()

        self.app.dependency_overrides[get_db_session] = override_db_session

        self.signal_repository_patch = patch.object(
            signal_stats_router,
            "SignalRepository",
            FakeSignalRepository,
        )
        self.ohlcv_repository_patch = patch.object(
            anomalies_router,
            "OhlcvRepository",
            FakeOhlcvRepository,
        )
        self.signal_repository_patch.start()
        self.ohlcv_repository_patch.start()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.signal_repository_patch.stop()
        self.ohlcv_repository_patch.stop()

    def test_signal_stats_routes_list_and_summary(self) -> None:
        now = datetime(2026, 4, 5, tzinfo=timezone.utc)
        pending_signal = SimpleNamespace(
            id=301,
            symbol="AAPL",
            signal_type="buy",
            status="pending",
            entry_price=190.25,
            stop_loss=184.5,
            take_profit_1=197.0,
            take_profit_2=201.0,
            take_profit_3=None,
            probability=0.84,
            confidence=0.79,
            risk_reward_ratio=2.1,
            sfp_validated=True,
            chooch_validated=False,
            fvg_validated=True,
            validation_status="validated",
            atr_value=3.2,
            atr_multiplier=2.0,
            indicators=json.dumps({"source": "scanner", "market_regime": "bull"}),
            reasoning="trend continuation",
            generated_at=now - timedelta(hours=2),
            triggered_at=None,
            expired_at=None,
        )
        active_signal = SimpleNamespace(
            id=302,
            symbol="MSFT",
            signal_type="sell",
            status="active",
            entry_price=420.0,
            stop_loss=428.0,
            take_profit_1=410.0,
            take_profit_2=404.0,
            take_profit_3=398.0,
            probability=0.61,
            confidence=0.67,
            risk_reward_ratio=1.8,
            sfp_validated=False,
            chooch_validated=True,
            fvg_validated=False,
            validation_status="choch",
            atr_value=4.8,
            atr_multiplier=2.5,
            indicators=json.dumps({"source": "scanner", "market_regime": "range"}),
            reasoning="mean reversion fade",
            generated_at=now - timedelta(hours=5),
            triggered_at=now - timedelta(hours=4),
            expired_at=None,
        )

        FakeSignalRepository.records = [pending_signal, active_signal]
        FakeSignalRepository.summary_payload = {
            "window_hours": 48,
            "generated_after": now - timedelta(hours=48),
            "total_signals": 2,
            "pending_signals": 1,
            "active_signals": 1,
            "triggered_signals": 0,
            "expired_signals": 0,
            "cancelled_signals": 0,
            "buy_signals": 1,
            "sell_signals": 1,
            "split_buy_signals": 0,
            "split_sell_signals": 0,
            "avg_probability": 0.725,
            "avg_confidence": 0.73,
            "top_symbols": [
                {"symbol": "AAPL", "count": 1},
                {"symbol": "MSFT", "count": 1},
            ],
        }

        summary_response = self.client.get(
            "/v1/admin/signal-stats/summary",
            params={"window_hours": 48},
        )
        self.assertEqual(summary_response.status_code, 200)
        self.assertEqual(
            summary_response.json(),
            {
                "window_hours": 48,
                "generated_after": "2026-04-03T00:00:00Z",
                "total_signals": 2,
                "pending_signals": 1,
                "active_signals": 1,
                "triggered_signals": 0,
                "expired_signals": 0,
                "cancelled_signals": 0,
                "buy_signals": 1,
                "sell_signals": 1,
                "split_buy_signals": 0,
                "split_sell_signals": 0,
                "avg_probability": 0.725,
                "avg_confidence": 0.73,
                "top_symbols": [
                    {"symbol": "AAPL", "count": 1},
                    {"symbol": "MSFT", "count": 1},
                ],
            },
        )

        list_response = self.client.get(
            "/v1/admin/signal-stats",
            params={
                "status": "pending",
                "signal_type": "buy",
                "validation_status": "validated",
                "limit": 25,
                "offset": 0,
            },
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(
            list_response.json(),
            {
                "data": [
                    {
                        "id": 301,
                        "symbol": "AAPL",
                        "signal_type": "buy",
                        "status": "pending",
                        "entry_price": 190.25,
                        "stop_loss": 184.5,
                        "take_profit_1": 197.0,
                        "take_profit_2": 201.0,
                        "take_profit_3": None,
                        "probability": 0.84,
                        "confidence": 0.79,
                        "risk_reward_ratio": 2.1,
                        "sfp_validated": True,
                        "chooch_validated": False,
                        "fvg_validated": True,
                        "validation_status": "validated",
                        "atr_value": 3.2,
                        "atr_multiplier": 2.0,
                        "indicators": {"source": "scanner", "market_regime": "bull"},
                        "reasoning": "trend continuation",
                        "generated_at": "2026-04-04T22:00:00Z",
                        "triggered_at": None,
                        "expired_at": None,
                    }
                ],
                "total": 1,
                "limit": 25,
                "offset": 0,
                "has_more": False,
            },
        )

    def test_ohlcv_anomalies_route_lists_filtered_rows(self) -> None:
        now = datetime(2026, 4, 5, tzinfo=timezone.utc)
        anomaly_error = SimpleNamespace(
            id=901,
            symbol="AAPL",
            timeframe="1d",
            bar_time=now - timedelta(days=1),
            anomaly_code="invalid_row",
            severity="error",
            details=json.dumps({"field": "close", "row": 12}),
            source="polygon",
            quarantined_at=now - timedelta(hours=6),
        )
        anomaly_warning = SimpleNamespace(
            id=902,
            symbol="MSFT",
            timeframe="1h",
            bar_time=now - timedelta(hours=2),
            anomaly_code="missing_bar_gap",
            severity="warning",
            details=json.dumps({"previous_timestamp": "2026-04-04T20:00:00+00:00"}),
            source="binance",
            quarantined_at=now - timedelta(hours=2),
        )

        FakeOhlcvRepository.anomalies = [anomaly_error, anomaly_warning]

        response = self.client.get(
            "/v1/admin/anomalies/ohlcv",
            params={"severity": "error", "limit": 10, "offset": 0},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "data": [
                    {
                        "id": 901,
                        "symbol": "AAPL",
                        "timeframe": "1d",
                        "bar_time": "2026-04-04T00:00:00Z",
                        "anomaly_code": "invalid_row",
                        "severity": "error",
                        "details": {"field": "close", "row": 12},
                        "source": "polygon",
                        "quarantined_at": "2026-04-04T18:00:00Z",
                    }
                ],
                "total": 1,
                "limit": 10,
                "offset": 0,
                "has_more": False,
            },
        )
