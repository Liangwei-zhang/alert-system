from __future__ import annotations

from types import MethodType, SimpleNamespace
from unittest import IsolatedAsyncioTestCase

from domains.signals.desktop_signal_service import DesktopSignalService
from domains.signals.schemas import DesktopSignalRequest


class DesktopSignalServiceTest(IsolatedAsyncioTestCase):
    async def test_ingest_desktop_signal_enriches_analysis_with_exit_levels(self) -> None:
        service = DesktopSignalService(session=object())
        captured: dict[str, object] = {"published": []}

        async def fake_find_recent_duplicate(**kwargs):
            return None

        async def fake_create_signal(payload):
            captured["payload"] = payload
            return SimpleNamespace(id=321)

        async def fake_publish_after_commit(*, topic, key, payload):
            published = captured.setdefault("published", [])
            assert isinstance(published, list)
            published.append({"topic": topic, "key": key, "payload": payload})

        service.repository.find_recent_duplicate = fake_find_recent_duplicate
        service.repository.create_signal = fake_create_signal
        service.outbox.publish_after_commit = fake_publish_after_commit

        request = DesktopSignalRequest.model_validate(
            {
                "source": "desktop-terminal",
                "emitted_at": "2026-04-11T00:00:00Z",
                "alert": {
                    "symbol": "aapl",
                    "type": "buy",
                    "score": 87,
                    "price": 150.25,
                    "reasons": ["breakout"],
                    "confidence": 90,
                    "probability": 0.82,
                    "strategy_window": "1h",
                    "market_regime": "trend",
                },
                "analysis": {
                    "cooldown_minutes": 60,
                    "strategy_window": "1h",
                    "market_regime": "trend",
                    "atr_value": 5.0,
                    "atr_multiplier": 2.0,
                    "risk_reward_ratio": 2.4,
                },
            }
        )

        result = await service.ingest_desktop_signal(request)

        self.assertEqual(result["status"], "accepted")
        payload = captured["payload"]
        assert isinstance(payload, dict)
        self.assertEqual(payload["stop_loss"], 140.25)
        self.assertEqual(payload["take_profit_1"], 157.75)
        self.assertEqual(payload["analysis"]["exit_levels"]["source"], "server_default")
        published = captured["published"]
        assert isinstance(published, list)
        self.assertEqual(len(published), 2)
        self.assertEqual(
            published[0]["payload"]["analysis"]["exit_levels"]["source"],
            "server_default",
        )

    async def test_ingest_desktop_signal_applies_active_calibration_snapshot_when_missing(self) -> None:
        service = DesktopSignalService(session=object())
        captured: dict[str, object] = {"published": []}

        async def fake_find_recent_duplicate(**kwargs):
            return None

        async def fake_create_signal(payload):
            captured["payload"] = payload
            return SimpleNamespace(id=654)

        async def fake_publish_after_commit(*, topic, key, payload):
            published = captured.setdefault("published", [])
            assert isinstance(published, list)
            published.append({"topic": topic, "key": key, "payload": payload})

        async def fake_load_active_calibration_snapshot(self):
            return {
                "version": "signals-v2-review-20260411",
                "source": "manual_review",
                "strategy_weights": {"trend_continuation": 1.12},
                "score_multipliers": {"confidence": 1.08},
            }

        service.repository.find_recent_duplicate = fake_find_recent_duplicate
        service.repository.create_signal = fake_create_signal
        service.outbox.publish_after_commit = fake_publish_after_commit
        service.load_active_calibration_snapshot = MethodType(
            fake_load_active_calibration_snapshot,
            service,
        )

        request = DesktopSignalRequest.model_validate(
            {
                "source": "desktop-terminal",
                "emitted_at": "2026-04-11T00:00:00Z",
                "alert": {
                    "symbol": "msft",
                    "type": "buy",
                    "score": 84,
                    "price": 312.5,
                    "reasons": ["trend continuation"],
                    "confidence": 88,
                    "probability": 0.78,
                    "strategy_window": "1h",
                    "market_regime": "trend",
                },
                "analysis": {
                    "cooldown_minutes": 60,
                    "strategy_window": "1h",
                    "market_regime": "trend",
                    "atr_value": 4.0,
                    "atr_multiplier": 2.0,
                    "risk_reward_ratio": 2.1,
                    "strategy_selection": {"strategy": "trend_continuation", "source": "client"},
                },
            }
        )

        result = await service.ingest_desktop_signal(request)

        self.assertEqual(result["status"], "accepted")
        payload = captured["payload"]
        assert isinstance(payload, dict)
        self.assertEqual(payload["analysis"]["calibration_version"], "signals-v2-review-20260411")
        self.assertEqual(
            payload["analysis"]["strategy_selection"]["calibration_version"],
            "signals-v2-review-20260411",
        )
        self.assertEqual(
            payload["analysis"]["calibration_snapshot"]["strategy_weights"]["trend_continuation"],
            1.12,
        )
        published = captured["published"]
        assert isinstance(published, list)
        self.assertEqual(
            published[0]["payload"]["analysis"]["calibration_version"],
            "signals-v2-review-20260411",
        )