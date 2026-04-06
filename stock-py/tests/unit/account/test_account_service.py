import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from domains.account.schemas import UpdateAccountRequest
from domains.account.service import AccountService
from infra.core.errors import AppError


class FakeAccountRepository:
    def __init__(self, profile_user=None, profile_account=None, dashboard=None) -> None:
        self.profile_user = profile_user
        self.profile_account = profile_account
        self.dashboard = dashboard
        self.profile_calls = 0
        self.dashboard_calls = 0
        self.session = SimpleNamespace(info={})
        self.upsert_account_calls: list[dict] = []
        self.update_user_profile_calls: list[dict] = []

    async def get_profile(self, user_id: int):
        self.profile_calls += 1
        return self.profile_user, self.profile_account

    async def get_dashboard(self, user_id: int):
        self.dashboard_calls += 1
        return self.dashboard

    async def upsert_account(self, user_id: int, total_capital, currency) -> None:
        self.upsert_account_calls.append(
            {
                "user_id": user_id,
                "total_capital": total_capital,
                "currency": currency,
            }
        )

    async def update_user_profile(
        self, user_id: int, name=None, locale=None, timezone_name=None
    ) -> None:
        self.update_user_profile_calls.append(
            {
                "user_id": user_id,
                "name": name,
                "locale": locale,
                "timezone_name": timezone_name,
            }
        )


class AccountServiceTest(unittest.TestCase):
    def test_get_dashboard_aggregates_portfolio_and_auto_activates_subscription(self) -> None:
        repository = FakeAccountRepository(
            dashboard={
                "user": SimpleNamespace(
                    name="QA User",
                    email="qa@example.com",
                    plan="pro",
                    locale="en-US",
                    timezone="UTC",
                    extra={"subscription": {"status": "paused", "last_sync_reason": "scanner"}},
                ),
                "account": SimpleNamespace(total_capital=10000, currency="USD"),
                "portfolio": [
                    SimpleNamespace(symbol="AAPL", shares=10, avg_cost=150, total_capital=1500),
                    SimpleNamespace(symbol="MSFT", shares=5, avg_cost=200, total_capital=1000),
                ],
                "watchlist": [
                    SimpleNamespace(symbol="AAPL", notify=True),
                    SimpleNamespace(symbol="NVDA", notify=False),
                ],
            }
        )

        response = asyncio.run(AccountService(repository).get_dashboard(user_id=42))

        self.assertEqual(response.account.portfolio_value, 2500.0)
        self.assertEqual(response.account.available_cash, 7500.0)
        self.assertEqual(response.account.portfolio_pct, 25.0)
        self.assertEqual(response.watchlist.total, 2)
        self.assertEqual(response.watchlist.notify_enabled, 1)
        self.assertEqual(response.portfolio[0].pct, 15.0)
        self.assertEqual(response.portfolio[1].pct, 10.0)
        self.assertEqual(response.subscription.status, "active")
        self.assertEqual(response.subscription.last_sync_reason, "scanner")
        self.assertTrue(response.subscription.checklist.has_capital)
        self.assertEqual(response.subscription.checklist.portfolio_count, 2)

    def test_get_profile_raises_when_user_is_missing(self) -> None:
        service = AccountService(FakeAccountRepository(profile_user=None, profile_account=None))

        with self.assertRaises(AppError):
            asyncio.run(service.get_profile(user_id=404))

    def test_get_profile_returns_cached_payload_without_hitting_repository(self) -> None:
        repository = FakeAccountRepository(profile_user=None, profile_account=None)
        service = AccountService(repository)
        cached_payload = {
            "user": {
                "name": "Cached QA User",
                "email": "qa@example.com",
                "plan": "pro",
                "locale": "en-US",
                "timezone": "UTC",
            },
            "account": {
                "total_capital": 12000.0,
                "currency": "USD",
            },
        }

        with patch(
            "domains.account.service.get_or_load_account_profile",
            AsyncMock(return_value=cached_payload),
        ) as cache_loader:
            response = asyncio.run(service.get_profile(user_id=42))

        self.assertEqual(repository.profile_calls, 0)
        self.assertEqual(response.user.name, "Cached QA User")
        self.assertEqual(response.account.total_capital, 12000.0)
        cache_loader.assert_awaited_once()

    def test_get_profile_caches_repository_result_on_miss(self) -> None:
        repository = FakeAccountRepository(
            profile_user=SimpleNamespace(
                name="QA User",
                email="qa@example.com",
                plan="pro",
                locale="en-US",
                timezone="UTC",
            ),
            profile_account=SimpleNamespace(total_capital=8000, currency="USD"),
        )
        service = AccountService(repository)

        async def invoke_loader(_user_id: int, loader):
            return await loader()

        with patch(
            "domains.account.service.get_or_load_account_profile",
            AsyncMock(side_effect=invoke_loader),
        ) as cache_loader:
            response = asyncio.run(service.get_profile(user_id=42))

        self.assertEqual(repository.profile_calls, 1)
        cache_loader.assert_awaited_once()
        self.assertEqual(cache_loader.await_args.args[0], 42)
        self.assertEqual(response.user.email, "qa@example.com")

    def test_update_profile_skips_account_upsert_without_account_fields(self) -> None:
        repository = FakeAccountRepository(
            profile_user=SimpleNamespace(
                name="Renamed QA User",
                email="qa@example.com",
                plan="pro",
                locale="zh-TW",
                timezone="Asia/Taipei",
            ),
            profile_account=SimpleNamespace(total_capital=8000, currency="USD"),
        )
        service = AccountService(repository)

        response = asyncio.run(
            service.update_profile(
                user_id=7,
                request=UpdateAccountRequest(
                    name="Renamed QA User", locale="zh-TW", timezone="Asia/Taipei"
                ),
            )
        )

        self.assertEqual(repository.upsert_account_calls, [])
        self.assertEqual(
            repository.update_user_profile_calls,
            [
                {
                    "user_id": 7,
                    "name": "Renamed QA User",
                    "locale": "zh-TW",
                    "timezone_name": "Asia/Taipei",
                }
            ],
        )
        self.assertEqual(response.user.name, "Renamed QA User")
        self.assertEqual(response.account.total_capital, 8000.0)

    def test_get_dashboard_returns_cached_payload_without_hitting_repository(self) -> None:
        repository = FakeAccountRepository(dashboard=None)
        service = AccountService(repository)
        cached_payload = {
            "user": {
                "name": "Cached QA User",
                "email": "qa@example.com",
                "plan": "pro",
                "locale": "en-US",
                "timezone": "UTC",
            },
            "account": {
                "total_capital": 12000.0,
                "currency": "USD",
                "portfolio_value": 2500.0,
                "available_cash": 9500.0,
                "portfolio_pct": 20.8,
            },
            "portfolio": [],
            "watchlist": {"total": 2, "notify_enabled": 1},
            "subscription": {
                "status": "active",
                "started_at": None,
                "last_synced_at": None,
                "last_sync_reason": None,
                "checklist": {
                    "has_capital": True,
                    "currency": "USD",
                    "watchlist_count": 2,
                    "watchlist_notify_enabled": 1,
                    "portfolio_count": 0,
                    "push_device_count": 0,
                },
            },
        }

        with patch(
            "domains.account.service.get_or_load_account_dashboard",
            AsyncMock(return_value=cached_payload),
        ) as cache_loader:
            response = asyncio.run(service.get_dashboard(user_id=42))

        self.assertEqual(repository.dashboard_calls, 0)
        self.assertEqual(response.user.name, "Cached QA User")
        cache_loader.assert_awaited_once()

    def test_get_dashboard_caches_repository_result_on_miss(self) -> None:
        repository = FakeAccountRepository(
            dashboard={
                "user": SimpleNamespace(
                    name="QA User",
                    email="qa@example.com",
                    plan="pro",
                    locale="en-US",
                    timezone="UTC",
                    extra={"subscription": {"status": "active"}},
                ),
                "account": SimpleNamespace(total_capital=10000, currency="USD"),
                "portfolio": [
                    SimpleNamespace(symbol="AAPL", shares=10, avg_cost=150, total_capital=1500)
                ],
                "watchlist": [SimpleNamespace(symbol="AAPL", notify=True)],
            }
        )
        service = AccountService(repository)

        async def invoke_loader(_user_id: int, loader):
            return await loader()

        with patch(
            "domains.account.service.get_or_load_account_dashboard",
            AsyncMock(side_effect=invoke_loader),
        ) as cache_loader:
            response = asyncio.run(service.get_dashboard(user_id=42))

        self.assertEqual(repository.dashboard_calls, 1)
        cache_loader.assert_awaited_once()
        self.assertEqual(cache_loader.await_args.args[0], 42)
        self.assertEqual(response.account.portfolio_value, 1500.0)

    def test_update_profile_schedules_profile_and_dashboard_invalidation(self) -> None:
        repository = FakeAccountRepository(
            profile_user=SimpleNamespace(
                name="Updated",
                email="qa@example.com",
                plan="pro",
                locale="zh-TW",
                timezone="Asia/Taipei",
            ),
            profile_account=SimpleNamespace(total_capital=9000, currency="USD"),
        )
        service = AccountService(repository)

        with (
            patch(
                "domains.account.service.schedule_invalidate_account_dashboard"
            ) as dashboard_invalidator,
            patch(
                "domains.account.service.schedule_invalidate_account_profile"
            ) as profile_invalidator,
            patch(
                "domains.account.service.get_or_load_account_profile", AsyncMock()
            ) as profile_cache_loader,
        ):
            asyncio.run(
                service.update_profile(
                    user_id=7,
                    request=UpdateAccountRequest(name="Updated"),
                )
            )

        dashboard_invalidator.assert_called_once_with(repository.session, 7)
        profile_invalidator.assert_called_once_with(repository.session, 7)
        profile_cache_loader.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
