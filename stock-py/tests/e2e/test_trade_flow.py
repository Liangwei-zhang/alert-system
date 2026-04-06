from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from domains.trades.service import TradeService
from infra.db.models.trades import TradeAction, TradeStatus
from tests.helpers.app_client import PublicApiClient


def test_trade_flow(authenticated_public_api_client: PublicApiClient, monkeypatch) -> None:
    now = datetime(2026, 4, 4, tzinfo=timezone.utc)
    trade = SimpleNamespace(
        id="trade-1",
        user_id=42,
        symbol="AAPL",
        action=TradeAction.BUY,
        suggested_shares=10,
        suggested_price=150.0,
        suggested_amount=1500.0,
        status=TradeStatus.PENDING,
        expires_at=now + timedelta(hours=1),
        link_token="token-123",
        link_sig="sig-123",
    )
    calls: dict[str, object] = {}

    async def fake_get_trade_by_id(self, trade_id: str):
        calls.setdefault("get_trade_by_id", []).append(trade_id)
        return trade

    async def fake_get_trade_for_user(self, trade_id: str, user_id: int):
        calls.setdefault("get_trade_for_user", []).append(
            {"trade_id": trade_id, "user_id": user_id}
        )
        return trade

    async def fake_get_trade_info_by_id(self, trade_id: str):
        calls.setdefault("get_trade_info_by_id", []).append(trade_id)
        return trade

    async def fake_get_trade_info_for_user(self, trade_id: str, user_id: int):
        calls.setdefault("get_trade_info_for_user", []).append(
            {"trade_id": trade_id, "user_id": user_id}
        )
        return trade

    def fake_verify_link_token(self, trade_obj, token: str) -> bool:
        calls.setdefault("verify_link_token", []).append({"trade_id": trade_obj.id, "token": token})
        return token == "token-123"

    def fake_is_expired(self, trade_obj) -> bool:
        calls.setdefault("is_expired", []).append(trade_obj.id)
        return False

    def fake_get_unavailable_error(self, trade_obj):
        calls.setdefault("get_unavailable_error", []).append(trade_obj.id)
        return None

    async def fake_confirm_trade(self, trade_obj, actual_shares=None, actual_price=None) -> float:
        calls.setdefault("confirm_trade", []).append(
            {
                "trade_id": trade_obj.id,
                "actual_shares": actual_shares,
                "actual_price": actual_price,
            }
        )
        return round(float(actual_shares) * float(actual_price), 2)

    async def fake_ignore_trade(self, trade_obj) -> bool:
        calls.setdefault("ignore_trade", []).append(trade_obj.id)
        return True

    async def fake_adjust_trade(
        self, trade_obj, actual_shares: float, actual_price: float
    ) -> float:
        calls.setdefault("adjust_trade", []).append(
            {
                "trade_id": trade_obj.id,
                "actual_shares": actual_shares,
                "actual_price": actual_price,
            }
        )
        return round(actual_shares * actual_price, 2)

    async def fake_acknowledge_receipts(self, trade_obj) -> None:
        calls.setdefault("acknowledge_receipts", []).append(trade_obj.id)

    monkeypatch.setattr(TradeService, "get_trade_by_id", fake_get_trade_by_id)
    monkeypatch.setattr(TradeService, "get_trade_for_user", fake_get_trade_for_user)
    monkeypatch.setattr(TradeService, "get_trade_info_by_id", fake_get_trade_info_by_id)
    monkeypatch.setattr(TradeService, "get_trade_info_for_user", fake_get_trade_info_for_user)
    monkeypatch.setattr(TradeService, "verify_link_token", fake_verify_link_token)
    monkeypatch.setattr(TradeService, "is_expired", fake_is_expired)
    monkeypatch.setattr(TradeService, "get_unavailable_error", fake_get_unavailable_error)
    monkeypatch.setattr(TradeService, "confirm_trade", fake_confirm_trade)
    monkeypatch.setattr(TradeService, "ignore_trade", fake_ignore_trade)
    monkeypatch.setattr(TradeService, "adjust_trade", fake_adjust_trade)
    monkeypatch.setattr(TradeService, "acknowledge_receipts", fake_acknowledge_receipts)

    public_info = authenticated_public_api_client.get(
        "/v1/trades/trade-1/info", params={"t": "token-123"}
    )
    assert public_info.status_code == 200
    assert public_info.json()["trade"]["id"] == "trade-1"
    assert public_info.json()["trade"]["status"] == "pending"

    app_info = authenticated_public_api_client.get("/v1/trades/trade-1/app-info")
    assert app_info.status_code == 200
    assert app_info.json()["trade"]["symbol"] == "AAPL"

    public_confirm = authenticated_public_api_client.post(
        "/v1/trades/trade-1/confirm",
        params={"action": "accept", "t": "token-123"},
    )
    assert public_confirm.status_code == 200
    assert public_confirm.json() == {
        "message": "Confirmed. Your portfolio has been updated automatically."
    }

    public_ignore = authenticated_public_api_client.post(
        "/v1/trades/trade-1/ignore",
        params={"t": "token-123"},
    )
    assert public_ignore.status_code == 200
    assert public_ignore.json() == {"message": "Trade ignored successfully"}

    public_adjust = authenticated_public_api_client.post(
        "/v1/trades/trade-1/adjust",
        params={"t": "token-123"},
        json={"actual_shares": 8, "actual_price": 152},
    )
    assert public_adjust.status_code == 200
    assert public_adjust.json() == {"message": "Actual execution recorded", "actual_amount": 1216.0}

    app_confirm = authenticated_public_api_client.post("/v1/trades/trade-1/app-confirm")
    assert app_confirm.status_code == 200
    assert app_confirm.json() == {"message": "Trade confirmed"}

    app_ignore = authenticated_public_api_client.post("/v1/trades/trade-1/app-ignore")
    assert app_ignore.status_code == 200
    assert app_ignore.json() == {"message": "Trade ignored"}

    app_adjust = authenticated_public_api_client.post(
        "/v1/trades/trade-1/app-adjust",
        json={"actual_shares": 9, "actual_price": 151},
    )
    assert app_adjust.status_code == 200
    assert app_adjust.json() == {"message": "Actual execution recorded", "actual_amount": 1359.0}

    assert calls["get_trade_info_by_id"] == ["trade-1"]
    assert calls["get_trade_info_for_user"] == [
        {"trade_id": "trade-1", "user_id": 42},
    ]
    assert calls["get_trade_by_id"] == ["trade-1", "trade-1", "trade-1"]
    assert calls["get_trade_for_user"] == [
        {"trade_id": "trade-1", "user_id": 42},
        {"trade_id": "trade-1", "user_id": 42},
        {"trade_id": "trade-1", "user_id": 42},
    ]
    assert calls["verify_link_token"] == [
        {"trade_id": "trade-1", "token": "token-123"},
        {"trade_id": "trade-1", "token": "token-123"},
        {"trade_id": "trade-1", "token": "token-123"},
        {"trade_id": "trade-1", "token": "token-123"},
    ]
    assert calls["confirm_trade"] == [
        {"trade_id": "trade-1", "actual_shares": 10.0, "actual_price": 150.0},
        {"trade_id": "trade-1", "actual_shares": 10.0, "actual_price": 150.0},
    ]
    assert calls["ignore_trade"] == ["trade-1", "trade-1"]
    assert calls["adjust_trade"] == [
        {"trade_id": "trade-1", "actual_shares": 8.0, "actual_price": 152.0},
        {"trade_id": "trade-1", "actual_shares": 9.0, "actual_price": 151.0},
    ]
    assert calls["acknowledge_receipts"] == [
        "trade-1",
        "trade-1",
        "trade-1",
        "trade-1",
        "trade-1",
        "trade-1",
    ]
