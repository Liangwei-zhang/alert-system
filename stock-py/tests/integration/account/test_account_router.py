from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.public_api.routers import account as account_router
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
from domains.subscription.schemas import StartSubscriptionResponse
from infra.security.auth import CurrentUser, require_user


class FakeAccountService:
    profile_response = None
    dashboard_response = None
    updated_profile_response = None
    calls: dict[str, list] = {}

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    @classmethod
    def reset(cls) -> None:
        cls.calls = {"get_profile": [], "get_dashboard": [], "update_profile": []}

    async def get_profile(self, user_id: int):
        self.calls["get_profile"].append(user_id)
        return self.profile_response

    async def get_dashboard(self, user_id: int):
        self.calls["get_dashboard"].append(user_id)
        return self.dashboard_response

    async def update_profile(self, user_id: int, data):
        self.calls["update_profile"].append({"user_id": user_id, "payload": data.model_dump()})
        return self.updated_profile_response


class FakeStartSubscriptionService:
    response = None
    calls: list[dict] = []

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    @classmethod
    def reset(cls) -> None:
        cls.calls = []

    async def start_subscription(self, user_id: int, data):
        self.calls.append({"user_id": user_id, "payload": data.model_dump()})
        return self.response


class AccountRouterIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        FakeAccountService.reset()
        FakeStartSubscriptionService.reset()

        self.app = FastAPI()
        self.app.include_router(account_router.router, prefix="/v1")

        async def override_require_user():
            return CurrentUser(user_id=42, plan="pro", scopes=["app"], is_admin=False)

        async def override_db_session():
            yield object()

        self.app.dependency_overrides[require_user] = override_require_user
        self.app.dependency_overrides[account_router.get_db_session] = override_db_session

        self.account_service_patch = patch.object(
            account_router, "AccountService", FakeAccountService
        )
        self.start_subscription_patch = patch.object(
            account_router, "StartSubscriptionService", FakeStartSubscriptionService
        )
        self.account_service_patch.start()
        self.start_subscription_patch.start()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.account_service_patch.stop()
        self.start_subscription_patch.stop()

    def test_account_router_returns_profile_dashboard_and_subscription_payloads(self) -> None:
        FakeAccountService.profile_response = AccountProfileEnvelope(
            user=UserProfileResponse(
                name="QA User",
                email="user@example.com",
                plan="pro",
                locale="en-US",
                timezone="UTC",
            ),
            account=AccountSummaryResponse(total_capital=10000.0, currency="USD"),
        )
        FakeAccountService.dashboard_response = AccountDashboardResponse(
            user=FakeAccountService.profile_response.user,
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
                    extra={
                        "sell_plan": {
                            "base_shares": 10,
                            "stages": [{"id": "tp1", "sell_pct": 0.25}],
                        }
                    },
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
        FakeAccountService.updated_profile_response = AccountProfileEnvelope(
            user=UserProfileResponse(
                name="Renamed QA User",
                email="user@example.com",
                plan="pro",
                locale="zh-TW",
                timezone="Asia/Taipei",
            ),
            account=AccountSummaryResponse(total_capital=12500.0, currency="USD"),
        )
        FakeStartSubscriptionService.response = StartSubscriptionResponse(
            message="訂閱已開始，監控快照已同步",
            subscription={
                "status": "active",
                "started_at": "2026-04-04T00:00:00+00:00",
                "watchlist_count": 1,
                "portfolio_count": 1,
            },
        )

        profile_response = self.client.get("/v1/account/profile")
        self.assertEqual(profile_response.status_code, 200)
        self.assertEqual(
            profile_response.json(),
            {
                "user": {
                    "name": "QA User",
                    "email": "user@example.com",
                    "plan": "pro",
                    "locale": "en-US",
                    "timezone": "UTC",
                },
                "account": {"total_capital": 10000.0, "currency": "USD"},
            },
        )

        dashboard_response = self.client.get("/v1/account/dashboard")
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertEqual(
            dashboard_response.json(),
            {
                "user": {
                    "name": "QA User",
                    "email": "user@example.com",
                    "plan": "pro",
                    "locale": "en-US",
                    "timezone": "UTC",
                },
                "account": {
                    "total_capital": 10000.0,
                    "currency": "USD",
                    "portfolio_value": 4500.0,
                    "available_cash": 5500.0,
                    "portfolio_pct": 45.0,
                },
                "portfolio": [
                    {
                        "symbol": "AAPL",
                        "shares": 10.0,
                        "avg_cost": 150.0,
                        "total_capital": 1500.0,
                        "pct": 15.0,
                        "extra": {
                            "sell_plan": {
                                "base_shares": 10,
                                "stages": [{"id": "tp1", "sell_pct": 0.25}],
                            }
                        },
                    }
                ],
                "watchlist": {"total": 2, "notify_enabled": 1},
                "subscription": {
                    "status": "active",
                    "started_at": "2026-04-04T00:00:00+00:00",
                    "last_synced_at": "2026-04-04T00:10:00+00:00",
                    "last_sync_reason": "manual_start",
                    "checklist": {
                        "has_capital": True,
                        "currency": "USD",
                        "watchlist_count": 2,
                        "watchlist_notify_enabled": 1,
                        "portfolio_count": 1,
                        "push_device_count": 0,
                    },
                },
            },
        )

        update_response = self.client.put(
            "/v1/account/profile",
            json={
                "name": "Renamed QA User",
                "locale": "zh-TW",
                "timezone": "Asia/Taipei",
                "total_capital": 12500,
                "currency": "USD",
            },
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(
            update_response.json(),
            {
                "user": {
                    "name": "Renamed QA User",
                    "email": "user@example.com",
                    "plan": "pro",
                    "locale": "zh-TW",
                    "timezone": "Asia/Taipei",
                },
                "account": {"total_capital": 12500.0, "currency": "USD"},
            },
        )

        subscription_response = self.client.post(
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
        self.assertEqual(subscription_response.status_code, 200)
        self.assertEqual(
            subscription_response.json(),
            {
                "message": "訂閱已開始，監控快照已同步",
                "subscription": {
                    "status": "active",
                    "started_at": "2026-04-04T00:00:00+00:00",
                    "watchlist_count": 1,
                    "portfolio_count": 1,
                },
            },
        )

        self.assertEqual(FakeAccountService.calls["get_profile"], [42])
        self.assertEqual(FakeAccountService.calls["get_dashboard"], [42])
        self.assertEqual(
            FakeAccountService.calls["update_profile"],
            [
                {
                    "user_id": 42,
                    "payload": {
                        "name": "Renamed QA User",
                        "locale": "zh-TW",
                        "timezone": "Asia/Taipei",
                        "total_capital": 12500.0,
                        "currency": "USD",
                    },
                }
            ],
        )
        self.assertEqual(
            FakeStartSubscriptionService.calls,
            [
                {
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
            ],
        )


if __name__ == "__main__":
    unittest.main()
