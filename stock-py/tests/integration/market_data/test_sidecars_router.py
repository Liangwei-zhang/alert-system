from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.public_api.routers import sidecars as sidecars_router
from domains.notifications.bridge_alert_service import BridgeAlertResult


class FakeMarketDataProxyService:
    calls: list[dict[str, str]] = []

    @classmethod
    def reset(cls) -> None:
        cls.calls = []

    async def get_historical(self, *, source: str, symbol: str, period: str = "1mo"):
        self.calls.append({"source": source, "symbol": symbol, "period": period})
        return {
            "source": source,
            "symbol": symbol.upper(),
            "period": period,
            "bars": [
                {
                    "date": datetime(2026, 4, 5, tzinfo=timezone.utc),
                    "open": 100.0,
                    "high": 110.0,
                    "low": 95.0,
                    "close": 108.0,
                    "volume": 123456,
                }
            ],
        }


class FakeBridgeAlertService:
    calls: list[dict] = []

    @classmethod
    def reset(cls) -> None:
        cls.calls = []

    async def send_alert(self, **kwargs):
        self.calls.append(kwargs)
        return BridgeAlertResult(
            resolved_user_ids=[42, 43],
            skipped_user_ids=[999],
            notification_ids=["notif-1", "notif-2"],
            outbox_ids=["outbox-1", "outbox-2", "outbox-3", "outbox-4"],
        )


class FakeTelegramRelayService:
    calls: list[dict[str, object]] = []

    @classmethod
    def reset(cls) -> None:
        cls.calls = []

    async def send_message(
        self,
        *,
        chat_id: str,
        text: str,
        parse_mode: str | None = None,
        disable_notification: bool = False,
    ):
        self.calls.append(
            {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_notification": disable_notification,
            }
        )
        return {"ok": True, "message_id": 123, "chat_id": chat_id}


class SidecarsRouterIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        FakeMarketDataProxyService.reset()
        FakeBridgeAlertService.reset()
        FakeTelegramRelayService.reset()

        self.market_data_service = FakeMarketDataProxyService()
        self.bridge_alert_service = FakeBridgeAlertService()
        self.telegram_service = FakeTelegramRelayService()

        self.app = FastAPI()
        self.app.include_router(sidecars_router.router)

        async def override_internal_secret() -> None:
            return None

        async def override_db_session():
            yield object()

        self.app.dependency_overrides[sidecars_router.require_internal_sidecar_secret] = (
            override_internal_secret
        )
        self.app.dependency_overrides[sidecars_router.get_db_session] = override_db_session
        self.app.dependency_overrides[sidecars_router._market_data_service] = (
            lambda: self.market_data_service
        )
        self.app.dependency_overrides[sidecars_router._telegram_relay_service] = (
            lambda: self.telegram_service
        )

        self.bridge_alert_patch = patch.object(
            sidecars_router,
            "_bridge_alert_service",
            lambda _session: self.bridge_alert_service,
        )

        self.bridge_alert_patch.start()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.bridge_alert_patch.stop()

    def test_market_data_proxy_routes_return_historical_payloads(self) -> None:
        yahoo_response = self.client.get("/api/yahoo/AAPL", params={"period": "3mo"})
        self.assertEqual(yahoo_response.status_code, 200)
        self.assertEqual(
            yahoo_response.json(),
            {
                "source": "yahoo",
                "symbol": "AAPL",
                "period": "3mo",
                "bars": [
                    {
                        "date": "2026-04-05T00:00:00Z",
                        "open": 100.0,
                        "high": 110.0,
                        "low": 95.0,
                        "close": 108.0,
                        "volume": 123456,
                    }
                ],
            },
        )

        binance_response = self.client.get("/api/binance/BTCUSDT", params={"period": "5d"})
        self.assertEqual(binance_response.status_code, 200)
        self.assertEqual(binance_response.json()["source"], "binance")
        self.assertEqual(
            FakeMarketDataProxyService.calls,
            [
                {"source": "yahoo", "symbol": "AAPL", "period": "3mo"},
                {"source": "binance", "symbol": "BTCUSDT", "period": "5d"},
            ],
        )

    def test_alert_bridge_and_telegram_relay_routes_queue_work(self) -> None:
        alerts_response = self.client.post(
            "/alerts",
            json={
                "user_ids": [42, 43, 999],
                "title": "Bridge alert",
                "body": "A new bridge alert arrived.",
                "channels": ["push", "email"],
                "notification_type": "bridge.alert",
                "ack_required": True,
                "metadata": {"bridge": "desktop"},
            },
        )
        self.assertEqual(alerts_response.status_code, 200)
        self.assertEqual(
            alerts_response.json(),
            {
                "message": "Bridge alert queued",
                "created_notifications": 2,
                "requested_outbox": 4,
                "resolved_user_ids": [42, 43],
                "skipped_user_ids": [999],
                "notification_ids": ["notif-1", "notif-2"],
                "outbox_ids": ["outbox-1", "outbox-2", "outbox-3", "outbox-4"],
                "channels": ["email", "push"],
            },
        )
        self.assertEqual(len(FakeBridgeAlertService.calls), 1)
        self.assertEqual(FakeBridgeAlertService.calls[0]["user_ids"], [42, 43, 999])
        self.assertEqual(FakeBridgeAlertService.calls[0]["channels"], ["email", "push"])

        telegram_response = self.client.post(
            "/api/telegram",
            json={
                "chat_id": "-100123456",
                "text": "relay me",
                "parse_mode": "Markdown",
                "disable_notification": True,
            },
        )
        self.assertEqual(telegram_response.status_code, 200)
        self.assertEqual(
            telegram_response.json(),
            {
                "message": "Telegram relay delivered",
                "ok": True,
                "message_id": 123,
                "chat_id": "-100123456",
            },
        )
        self.assertEqual(
            FakeTelegramRelayService.calls,
            [
                {
                    "chat_id": "-100123456",
                    "text": "relay me",
                    "parse_mode": "Markdown",
                    "disable_notification": True,
                }
            ],
        )