from __future__ import annotations

from datetime import datetime, timezone

from domains.account.schemas import (
    AccountDashboardDetailResponse,
    AccountDashboardResponse,
    AccountProfileEnvelope,
    AccountSummaryResponse,
    DashboardPortfolioItem,
    DashboardWatchlistSummary,
    SubscriptionChecklistResponse,
    SubscriptionStateResponse,
    UserProfileResponse,
)
from domains.account.service import AccountService
from domains.portfolio.schemas import PortfolioItemResponse
from domains.portfolio.service import PortfolioService
from domains.subscription.schemas import StartSubscriptionResponse
from domains.subscription.service import StartSubscriptionService
from domains.watchlist.schemas import WatchlistItemResponse
from domains.watchlist.service import WatchlistService
from tests.helpers.app_client import PublicApiClient


def test_subscription_flow(authenticated_public_api_client: PublicApiClient, monkeypatch) -> None:
    now = datetime(2026, 4, 4, tzinfo=timezone.utc)
    calls: dict[str, object] = {}

    profile_response = AccountProfileEnvelope(
        user=UserProfileResponse(
            name="QA User",
            email="user@example.com",
            plan="pro",
            locale="en-US",
            timezone="UTC",
        ),
        account=AccountSummaryResponse(total_capital=10000.0, currency="USD"),
    )
    updated_profile_response = AccountProfileEnvelope(
        user=UserProfileResponse(
            name="Renamed QA User",
            email="user@example.com",
            plan="pro",
            locale="zh-TW",
            timezone="Asia/Taipei",
        ),
        account=AccountSummaryResponse(total_capital=12500.0, currency="USD"),
    )
    dashboard_response = AccountDashboardResponse(
        user=profile_response.user,
        account=AccountDashboardDetailResponse(
            total_capital=10000.0,
            currency="USD",
            portfolio_value=4500.0,
            available_cash=5500.0,
            portfolio_pct=45.0,
        ),
        portfolio=[
            DashboardPortfolioItem(
                symbol="AAPL",
                shares=10,
                avg_cost=150.0,
                total_capital=1500.0,
                pct=15.0,
            )
        ],
        watchlist=DashboardWatchlistSummary(total=2, notify_enabled=1),
        subscription=SubscriptionStateResponse(
            status="active",
            started_at="2026-04-04T00:00:00+00:00",
            last_synced_at="2026-04-04T00:10:00+00:00",
            last_sync_reason="manual_start",
            checklist=SubscriptionChecklistResponse(
                has_capital=True,
                currency="USD",
                watchlist_count=2,
                watchlist_notify_enabled=1,
                portfolio_count=1,
                push_device_count=0,
            ),
        ),
    )
    created_watchlist_item = WatchlistItemResponse(
        id=1,
        symbol="AAPL",
        notify=True,
        min_score=70,
        created_at=now,
    )
    updated_watchlist_item = WatchlistItemResponse(
        id=1,
        symbol="AAPL",
        notify=False,
        min_score=75,
        created_at=now,
    )
    created_portfolio_item = PortfolioItemResponse(
        id=1,
        symbol="AAPL",
        shares=10,
        avg_cost=150.0,
        total_capital=1500.0,
        target_profit=0.2,
        stop_loss=0.1,
        notify=True,
        notes="starter position",
        updated_at=now,
    )
    updated_portfolio_item = PortfolioItemResponse(
        id=1,
        symbol="AAPL",
        shares=12,
        avg_cost=148.0,
        total_capital=1776.0,
        target_profit=0.25,
        stop_loss=0.08,
        notify=False,
        notes="scaled in",
        updated_at=now,
    )
    subscription_response = StartSubscriptionResponse(
        message="訂閱已開始，監控快照已同步",
        subscription={
            "status": "active",
            "started_at": "2026-04-04T00:00:00+00:00",
            "watchlist_count": 1,
            "portfolio_count": 1,
        },
    )

    async def fake_get_profile(self, user_id: int) -> AccountProfileEnvelope:
        calls["get_profile"] = user_id
        return profile_response

    async def fake_get_dashboard(self, user_id: int) -> AccountDashboardResponse:
        calls["get_dashboard"] = user_id
        return dashboard_response

    async def fake_update_profile(self, user_id: int, request) -> AccountProfileEnvelope:
        calls["update_profile"] = {
            "user_id": user_id,
            "payload": request.model_dump(),
        }
        return updated_profile_response

    async def fake_add_item(self, user_id: int, plan: str, request) -> WatchlistItemResponse:
        calls["create_watchlist"] = {
            "user_id": user_id,
            "plan": plan,
            "payload": request.model_dump(),
        }
        return created_watchlist_item

    async def fake_update_item(self, user_id: int, item_id: int, request) -> WatchlistItemResponse:
        calls["update_watchlist"] = {
            "user_id": user_id,
            "item_id": item_id,
            "payload": request.model_dump(exclude_unset=True),
        }
        return updated_watchlist_item

    async def fake_delete_item(self, user_id: int, item_id: int) -> None:
        calls["delete_watchlist"] = {"user_id": user_id, "item_id": item_id}

    async def fake_add_position(self, user_id: int, plan: str, request) -> PortfolioItemResponse:
        calls["create_portfolio"] = {
            "user_id": user_id,
            "plan": plan,
            "payload": request.model_dump(),
        }
        return created_portfolio_item

    async def fake_update_position(
        self, user_id: int, item_id: int, request
    ) -> PortfolioItemResponse:
        calls["update_portfolio"] = {
            "user_id": user_id,
            "item_id": item_id,
            "payload": request.model_dump(exclude_unset=True),
        }
        return updated_portfolio_item

    async def fake_delete_position(self, user_id: int, item_id: int) -> None:
        calls["delete_portfolio"] = {"user_id": user_id, "item_id": item_id}

    async def fake_start_subscription(self, user_id: int, request) -> StartSubscriptionResponse:
        calls["start_subscription"] = {
            "user_id": user_id,
            "payload": request.model_dump(),
        }
        return subscription_response

    monkeypatch.setattr(AccountService, "get_profile", fake_get_profile)
    monkeypatch.setattr(AccountService, "get_dashboard", fake_get_dashboard)
    monkeypatch.setattr(AccountService, "update_profile", fake_update_profile)
    monkeypatch.setattr(WatchlistService, "add_item", fake_add_item)
    monkeypatch.setattr(WatchlistService, "update_item", fake_update_item)
    monkeypatch.setattr(WatchlistService, "delete_item", fake_delete_item)
    monkeypatch.setattr(PortfolioService, "add_position", fake_add_position)
    monkeypatch.setattr(PortfolioService, "update_position", fake_update_position)
    monkeypatch.setattr(PortfolioService, "delete_position", fake_delete_position)
    monkeypatch.setattr(StartSubscriptionService, "start_subscription", fake_start_subscription)

    profile_result = authenticated_public_api_client.get("/v1/account/profile")
    assert profile_result.status_code == 200
    assert profile_result.json()["user"]["email"] == "user@example.com"

    dashboard_result = authenticated_public_api_client.get("/v1/account/dashboard")
    assert dashboard_result.status_code == 200
    assert dashboard_result.json()["subscription"]["status"] == "active"

    update_profile_result = authenticated_public_api_client.put(
        "/v1/account/profile",
        json={
            "name": "Renamed QA User",
            "locale": "zh-TW",
            "timezone": "Asia/Taipei",
            "total_capital": 12500,
            "currency": "USD",
        },
    )
    assert update_profile_result.status_code == 200
    assert update_profile_result.json()["user"]["name"] == "Renamed QA User"

    create_watchlist_result = authenticated_public_api_client.post(
        "/v1/watchlist",
        json={"symbol": "AAPL", "notify": True, "min_score": 70},
    )
    assert create_watchlist_result.status_code == 201
    assert create_watchlist_result.json()["symbol"] == "AAPL"

    update_watchlist_result = authenticated_public_api_client.put(
        "/v1/watchlist/1",
        json={"notify": False, "min_score": 75},
    )
    assert update_watchlist_result.status_code == 200
    assert update_watchlist_result.json()["notify"] is False

    delete_watchlist_result = authenticated_public_api_client.delete("/v1/watchlist/1")
    assert delete_watchlist_result.status_code == 204

    create_portfolio_result = authenticated_public_api_client.post(
        "/v1/portfolio",
        json={
            "symbol": "AAPL",
            "shares": 10,
            "avg_cost": 150,
            "target_profit": 0.2,
            "stop_loss": 0.1,
            "notify": True,
            "notes": "starter position",
        },
    )
    assert create_portfolio_result.status_code == 201
    assert create_portfolio_result.json()["shares"] == 10

    update_portfolio_result = authenticated_public_api_client.put(
        "/v1/portfolio/1",
        json={
            "shares": 12,
            "avg_cost": 148,
            "target_profit": 0.25,
            "stop_loss": 0.08,
            "notify": False,
            "notes": "scaled in",
        },
    )
    assert update_portfolio_result.status_code == 200
    assert update_portfolio_result.json()["total_capital"] == 1776.0

    delete_portfolio_result = authenticated_public_api_client.delete("/v1/portfolio/1")
    assert delete_portfolio_result.status_code == 204

    start_subscription_result = authenticated_public_api_client.post(
        "/v1/account/start-subscription",
        json={
            "allow_empty_portfolio": False,
            "account": {"total_capital": 10000, "currency": "USD"},
            "watchlist": [{"symbol": "AAPL", "min_score": 70, "notify": True}],
            "portfolio": [
                {
                    "symbol": "AAPL",
                    "shares": 10,
                    "avg_cost": 150,
                    "target_profit": 0.2,
                    "stop_loss": 0.1,
                    "notify": True,
                    "notes": "starter position",
                }
            ],
        },
    )
    assert start_subscription_result.status_code == 200
    assert start_subscription_result.json()["subscription"]["status"] == "active"

    assert calls["get_profile"] == 42
    assert calls["get_dashboard"] == 42
    assert calls["update_profile"] == {
        "user_id": 42,
        "payload": {
            "name": "Renamed QA User",
            "locale": "zh-TW",
            "timezone": "Asia/Taipei",
            "total_capital": 12500.0,
            "currency": "USD",
        },
    }
    assert calls["create_watchlist"] == {
        "user_id": 42,
        "plan": "pro",
        "payload": {"symbol": "AAPL", "notify": True, "min_score": 70},
    }
    assert calls["update_watchlist"] == {
        "user_id": 42,
        "item_id": 1,
        "payload": {"notify": False, "min_score": 75},
    }
    assert calls["delete_watchlist"] == {"user_id": 42, "item_id": 1}
    assert calls["create_portfolio"] == {
        "user_id": 42,
        "plan": "pro",
        "payload": {
            "symbol": "AAPL",
            "shares": 10,
            "avg_cost": 150.0,
            "target_profit": 0.2,
            "stop_loss": 0.1,
            "notify": True,
            "notes": "starter position",
        },
    }
    assert calls["update_portfolio"] == {
        "user_id": 42,
        "item_id": 1,
        "payload": {
            "shares": 12,
            "avg_cost": 148.0,
            "target_profit": 0.25,
            "stop_loss": 0.08,
            "notify": False,
            "notes": "scaled in",
        },
    }
    assert calls["delete_portfolio"] == {"user_id": 42, "item_id": 1}
    assert calls["start_subscription"] == {
        "user_id": 42,
        "payload": {
            "allow_empty_portfolio": False,
            "account": {"total_capital": 10000.0, "currency": "USD"},
            "watchlist": [{"symbol": "AAPL", "min_score": 70, "notify": True}],
            "portfolio": [
                {
                    "symbol": "AAPL",
                    "shares": 10,
                    "avg_cost": 150.0,
                    "target_profit": 0.2,
                    "stop_loss": 0.1,
                    "notify": True,
                    "notes": "starter position",
                }
            ],
        },
    }
