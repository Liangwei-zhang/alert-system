from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.public_api.routers import trades as trades_router
from infra.db.models.trades import TradeAction, TradeStatus
from infra.security.auth import CurrentUser, require_user


class FakeTradeService:
    trade_by_id = None
    trade_for_user = None
    trade_info_by_id = None
    trade_info_for_user = None
    token_valid = True
    expired = False
    unavailable_error = None
    calls: dict[str, list] = {}

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    @classmethod
    def reset(cls) -> None:
        cls.trade_by_id = None
        cls.trade_for_user = None
        cls.trade_info_by_id = None
        cls.trade_info_for_user = None
        cls.token_valid = True
        cls.expired = False
        cls.unavailable_error = None
        cls.calls = {
            "get_trade_by_id": [],
            "get_trade_for_user": [],
            "get_trade_info_by_id": [],
            "get_trade_info_for_user": [],
            "verify_link_token": [],
            "is_expired": [],
            "get_unavailable_error": [],
            "serialize_trade": [],
            "confirm_trade": [],
            "ignore_trade": [],
            "adjust_trade": [],
            "acknowledge_receipts": [],
        }

    async def get_trade_by_id(self, trade_id: str):
        self.calls["get_trade_by_id"].append(trade_id)
        return self.trade_by_id

    async def get_trade_for_user(self, trade_id: str, user_id: int):
        self.calls["get_trade_for_user"].append({"trade_id": trade_id, "user_id": user_id})
        return self.trade_for_user

    async def get_trade_info_by_id(self, trade_id: str):
        self.calls["get_trade_info_by_id"].append(trade_id)
        return self.trade_info_by_id

    async def get_trade_info_for_user(self, trade_id: str, user_id: int):
        self.calls["get_trade_info_for_user"].append({"trade_id": trade_id, "user_id": user_id})
        return self.trade_info_for_user

    def verify_link_token(self, trade, token: str) -> bool:
        self.calls["verify_link_token"].append({"trade_id": trade.id, "token": token})
        return self.token_valid

    def is_expired(self, trade) -> bool:
        self.calls["is_expired"].append(trade.id)
        return self.expired

    def get_unavailable_error(self, trade) -> str | None:
        self.calls["get_unavailable_error"].append(trade.id)
        return self.unavailable_error

    def serialize_trade(self, trade) -> dict[str, object]:
        self.calls["serialize_trade"].append(trade.id)
        return {
            "id": trade.id,
            "symbol": trade.symbol,
            "action": trade.action.value,
            "suggested_shares": float(trade.suggested_shares),
            "suggested_price": float(trade.suggested_price),
            "suggested_amount": float(trade.suggested_amount),
            "status": trade.status.value,
        }

    async def confirm_trade(self, trade, actual_shares: float, actual_price: float) -> float:
        self.calls["confirm_trade"].append(
            {
                "trade_id": trade.id,
                "actual_shares": float(actual_shares),
                "actual_price": float(actual_price),
            }
        )
        return round(float(actual_shares) * float(actual_price), 2)

    async def ignore_trade(self, trade) -> bool:
        self.calls["ignore_trade"].append(trade.id)
        return True

    async def adjust_trade(self, trade, actual_shares: float, actual_price: float) -> float:
        self.calls["adjust_trade"].append(
            {
                "trade_id": trade.id,
                "actual_shares": float(actual_shares),
                "actual_price": float(actual_price),
            }
        )
        return round(float(actual_shares) * float(actual_price), 2)

    async def acknowledge_receipts(self, trade) -> None:
        self.calls["acknowledge_receipts"].append(trade.id)


class TradesRouterIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        FakeTradeService.reset()

        self.app = FastAPI()
        self.app.include_router(trades_router.router, prefix="/v1")

        async def override_require_user():
            return CurrentUser(user_id=42, plan="pro", scopes=["app"], is_admin=False)

        async def override_db_session():
            yield object()

        self.app.dependency_overrides[require_user] = override_require_user
        self.app.dependency_overrides[trades_router.get_db_session] = override_db_session

        self.trade_service_patch = patch.object(trades_router, "TradeService", FakeTradeService)
        self.trade_service_patch.start()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.trade_service_patch.stop()

    @staticmethod
    def _make_trade(status: TradeStatus = TradeStatus.PENDING):
        now = datetime(2026, 4, 5, tzinfo=timezone.utc)
        return SimpleNamespace(
            id="trade-1",
            user_id=42,
            symbol="AAPL",
            action=TradeAction.BUY,
            suggested_shares=10,
            suggested_price=150.0,
            suggested_amount=1500.0,
            status=status,
            expires_at=now + timedelta(hours=1),
            link_token="token-123",
            link_sig="sig-123",
        )

    def test_trades_router_returns_trade_info_html_and_command_payloads(self) -> None:
        trade = self._make_trade()
        FakeTradeService.trade_info_by_id = trade
        FakeTradeService.trade_info_for_user = trade
        FakeTradeService.trade_by_id = trade
        FakeTradeService.trade_for_user = trade

        public_info_response = self.client.get("/v1/trades/trade-1/info", params={"t": "token-123"})
        self.assertEqual(public_info_response.status_code, 200)
        self.assertEqual(
            public_info_response.json(),
            {
                "trade": {
                    "id": "trade-1",
                    "symbol": "AAPL",
                    "action": "buy",
                    "suggested_shares": 10.0,
                    "suggested_price": 150.0,
                    "suggested_amount": 1500.0,
                    "status": "pending",
                },
                "is_expired": False,
                "expires_at": "2026-04-05T01:00:00Z",
            },
        )

        app_info_response = self.client.get("/v1/trades/trade-1/app-info")
        self.assertEqual(app_info_response.status_code, 200)
        self.assertEqual(app_info_response.json()["trade"]["id"], "trade-1")

        html_response = self.client.get(
            "/v1/trades/trade-1/confirm", params={"action": "accept", "t": "token-123"}
        )
        self.assertEqual(html_response.status_code, 200)
        self.assertEqual(html_response.json()["content_type"], "text/html")
        self.assertIn("Confirm suggestion", html_response.json()["content"])
        self.assertIn("AAPL", html_response.json()["content"])
        self.assertIn(
            "/v1/trades/trade-1/confirm?action=accept&t=token-123", html_response.json()["content"]
        )

        confirm_response = self.client.post(
            "/v1/trades/trade-1/confirm",
            params={"action": "accept", "t": "token-123"},
        )
        self.assertEqual(confirm_response.status_code, 200)
        self.assertEqual(
            confirm_response.json(),
            {"message": "Confirmed. Your portfolio has been updated automatically."},
        )

        ignore_response = self.client.post("/v1/trades/trade-1/ignore", params={"t": "token-123"})
        self.assertEqual(ignore_response.status_code, 200)
        self.assertEqual(ignore_response.json(), {"message": "Trade ignored successfully"})

        adjust_response = self.client.post(
            "/v1/trades/trade-1/adjust",
            params={"t": "token-123"},
            json={"actual_shares": 8, "actual_price": 152},
        )
        self.assertEqual(adjust_response.status_code, 200)
        self.assertEqual(
            adjust_response.json(),
            {"message": "Actual execution recorded", "actual_amount": 1216.0},
        )

        app_confirm_response = self.client.post("/v1/trades/trade-1/app-confirm")
        self.assertEqual(app_confirm_response.status_code, 200)
        self.assertEqual(app_confirm_response.json(), {"message": "Trade confirmed"})

        app_ignore_response = self.client.post("/v1/trades/trade-1/app-ignore")
        self.assertEqual(app_ignore_response.status_code, 200)
        self.assertEqual(app_ignore_response.json(), {"message": "Trade ignored"})

        app_adjust_response = self.client.post(
            "/v1/trades/trade-1/app-adjust",
            json={"actual_shares": 9, "actual_price": 151},
        )
        self.assertEqual(app_adjust_response.status_code, 200)
        self.assertEqual(
            app_adjust_response.json(),
            {"message": "Actual execution recorded", "actual_amount": 1359.0},
        )

        self.assertEqual(FakeTradeService.calls["get_trade_info_by_id"], ["trade-1"])
        self.assertEqual(
            FakeTradeService.calls["get_trade_info_for_user"],
            [{"trade_id": "trade-1", "user_id": 42}],
        )
        self.assertEqual(
            FakeTradeService.calls["get_trade_by_id"],
            ["trade-1", "trade-1", "trade-1", "trade-1"],
        )
        self.assertEqual(
            FakeTradeService.calls["get_trade_for_user"],
            [
                {"trade_id": "trade-1", "user_id": 42},
                {"trade_id": "trade-1", "user_id": 42},
                {"trade_id": "trade-1", "user_id": 42},
            ],
        )
        self.assertEqual(
            FakeTradeService.calls["verify_link_token"],
            [
                {"trade_id": "trade-1", "token": "token-123"},
                {"trade_id": "trade-1", "token": "token-123"},
                {"trade_id": "trade-1", "token": "token-123"},
                {"trade_id": "trade-1", "token": "token-123"},
                {"trade_id": "trade-1", "token": "token-123"},
            ],
        )
        self.assertEqual(
            FakeTradeService.calls["confirm_trade"],
            [
                {"trade_id": "trade-1", "actual_shares": 10.0, "actual_price": 150.0},
                {"trade_id": "trade-1", "actual_shares": 10.0, "actual_price": 150.0},
            ],
        )
        self.assertEqual(FakeTradeService.calls["ignore_trade"], ["trade-1", "trade-1"])
        self.assertEqual(
            FakeTradeService.calls["adjust_trade"],
            [
                {"trade_id": "trade-1", "actual_shares": 8.0, "actual_price": 152.0},
                {"trade_id": "trade-1", "actual_shares": 9.0, "actual_price": 151.0},
            ],
        )
        self.assertEqual(
            FakeTradeService.calls["acknowledge_receipts"],
            ["trade-1", "trade-1", "trade-1", "trade-1", "trade-1", "trade-1"],
        )

    def test_trades_router_handles_public_and_app_error_paths(self) -> None:
        trade = self._make_trade()
        FakeTradeService.trade_by_id = trade
        FakeTradeService.trade_for_user = trade

        missing_info_response = self.client.get(
            "/v1/trades/missing/info", params={"t": "token-123"}
        )
        self.assertEqual(missing_info_response.status_code, 404)
        self.assertEqual(missing_info_response.json(), {"detail": "Trade record not found"})

        FakeTradeService.token_valid = False
        invalid_html_response = self.client.get(
            "/v1/trades/trade-1/confirm", params={"action": "accept", "t": "bad-token"}
        )
        self.assertEqual(invalid_html_response.status_code, 200)
        self.assertEqual(invalid_html_response.json()["content_type"], "text/html")
        self.assertIn("invalid or no longer available", invalid_html_response.json()["content"])

        invalid_confirm_response = self.client.post(
            "/v1/trades/trade-1/confirm",
            params={"action": "accept", "t": "bad-token"},
        )
        self.assertEqual(invalid_confirm_response.status_code, 403)
        self.assertEqual(invalid_confirm_response.json(), {"detail": "Invalid link token"})

        FakeTradeService.token_valid = True
        FakeTradeService.expired = True
        expired_ignore_response = self.client.post(
            "/v1/trades/trade-1/ignore", params={"t": "token-123"}
        )
        self.assertEqual(expired_ignore_response.status_code, 400)
        self.assertEqual(expired_ignore_response.json(), {"detail": "This link has expired"})

        FakeTradeService.expired = False
        FakeTradeService.trade_by_id = self._make_trade(status=TradeStatus.CONFIRMED)
        processed_confirm_response = self.client.post(
            "/v1/trades/trade-1/confirm",
            params={"action": "accept", "t": "token-123"},
        )
        self.assertEqual(processed_confirm_response.status_code, 400)
        self.assertEqual(
            processed_confirm_response.json(),
            {"detail": "This trade has already been processed"},
        )

        FakeTradeService.trade_for_user = trade
        FakeTradeService.unavailable_error = "Trade is no longer available"
        app_confirm_response = self.client.post("/v1/trades/trade-1/app-confirm")
        self.assertEqual(app_confirm_response.status_code, 400)
        self.assertEqual(
            app_confirm_response.json(),
            {"detail": "Trade is no longer available"},
        )


if __name__ == "__main__":
    unittest.main()
