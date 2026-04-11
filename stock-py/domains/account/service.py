from __future__ import annotations

from domains.account.repository import AccountRepository
from domains.portfolio.extra_payload import deserialize_portfolio_extra
from domains.account.schemas import (
    AccountDashboardDetailResponse,
    AccountDashboardResponse,
    AccountProfileEnvelope,
    AccountSummaryResponse,
    DashboardPortfolioItem,
    DashboardWatchlistSummary,
    SubscriptionChecklistResponse,
    SubscriptionStateResponse,
    UpdateAccountRequest,
    UserProfileResponse,
)
from infra.cache.account_dashboard_cache import (
    get_or_load_account_dashboard,
    schedule_invalidate_account_dashboard,
)
from infra.cache.account_profile_cache import (
    get_or_load_account_profile,
    schedule_invalidate_account_profile,
)
from infra.core.errors import AppError


class AccountService:
    def __init__(self, repository: AccountRepository) -> None:
        self.repository = repository

    def _schedule_dashboard_invalidation(self, user_id: int) -> None:
        schedule_invalidate_account_dashboard(getattr(self.repository, "session", None), user_id)

    def _schedule_profile_invalidation(self, user_id: int) -> None:
        schedule_invalidate_account_profile(getattr(self.repository, "session", None), user_id)

    async def _build_profile_payload(self, user_id: int) -> dict:
        user, account = await self.repository.get_profile(user_id)
        if user is None:
            raise AppError("user_not_found", "User not found", status_code=404)

        return AccountProfileEnvelope(
            user=UserProfileResponse(
                name=user.name,
                email=user.email,
                plan=user.plan,
                locale=user.locale,
                timezone=user.timezone,
            ),
            account=AccountSummaryResponse(
                total_capital=float(account.total_capital) if account else 0,
                currency=account.currency if account else "USD",
            ),
        ).model_dump(mode="json")

    async def _build_dashboard_payload(self, user_id: int) -> dict:
        dashboard = await self.repository.get_dashboard(user_id)
        user = dashboard["user"]
        account = dashboard["account"]
        portfolio_positions = dashboard["portfolio"]
        watchlist_items = dashboard["watchlist"]

        if user is None:
            raise AppError("user_not_found", "User not found", status_code=404)

        total_capital = float(account.total_capital) if account else 0
        currency = account.currency if account else "USD"
        portfolio_value = sum(float(item.total_capital) for item in portfolio_positions)
        available_cash = total_capital - portfolio_value
        watchlist_count = len(watchlist_items)
        notify_enabled = sum(1 for item in watchlist_items if item.notify)
        portfolio_count = len(portfolio_positions)

        portfolio = [
            DashboardPortfolioItem(
                symbol=item.symbol,
                shares=float(item.shares),
                avg_cost=float(item.avg_cost),
                total_capital=float(item.total_capital),
                pct=(
                    round((float(item.total_capital) / total_capital * 100), 1)
                    if total_capital > 0
                    else 0
                ),
                extra=deserialize_portfolio_extra(getattr(item, "extra", None)),
            )
            for item in portfolio_positions
        ]

        subscription = self._build_subscription_state(
            extra=user.extra if isinstance(user.extra, dict) else {},
            total_capital=total_capital,
            currency=currency,
            watchlist_count=watchlist_count,
            watchlist_notify_enabled=notify_enabled,
            portfolio_count=portfolio_count,
        )

        return AccountDashboardResponse(
            user=UserProfileResponse(
                name=user.name,
                email=user.email,
                plan=user.plan,
                locale=user.locale,
                timezone=user.timezone,
            ),
            account=AccountDashboardDetailResponse(
                total_capital=total_capital,
                currency=currency,
                portfolio_value=round(portfolio_value, 2),
                available_cash=round(available_cash, 2),
                portfolio_pct=(
                    round((portfolio_value / total_capital * 100), 1) if total_capital > 0 else 0
                ),
            ),
            portfolio=portfolio,
            watchlist=DashboardWatchlistSummary(
                total=watchlist_count,
                notify_enabled=notify_enabled,
            ),
            subscription=subscription,
        ).model_dump(mode="json")

    def _build_subscription_state(
        self,
        extra: dict | None,
        total_capital: float,
        currency: str,
        watchlist_count: int,
        watchlist_notify_enabled: int,
        portfolio_count: int,
        push_device_count: int = 0,
    ) -> SubscriptionStateResponse:
        subscription = {}
        if extra and isinstance(extra, dict):
            raw = extra.get("subscription")
            if isinstance(raw, dict):
                subscription = raw

        status = subscription.get("status")
        if status not in {"active", "draft"}:
            status = (
                "active"
                if total_capital > 0 and (watchlist_count > 0 or portfolio_count > 0)
                else "draft"
            )

        return SubscriptionStateResponse(
            status=status,
            started_at=subscription.get("started_at"),
            last_synced_at=subscription.get("last_synced_at"),
            last_sync_reason=subscription.get("last_sync_reason"),
            checklist=SubscriptionChecklistResponse(
                has_capital=total_capital > 0,
                currency=currency,
                watchlist_count=watchlist_count,
                watchlist_notify_enabled=watchlist_notify_enabled,
                portfolio_count=portfolio_count,
                push_device_count=push_device_count,
            ),
        )

    async def get_profile(self, user_id: int, *, use_cache: bool = True) -> AccountProfileEnvelope:
        if use_cache:
            payload = await get_or_load_account_profile(
                user_id,
                lambda: self._build_profile_payload(user_id),
            )
        else:
            payload = await self._build_profile_payload(user_id)
        return AccountProfileEnvelope.model_validate(payload)

    async def get_dashboard(self, user_id: int) -> AccountDashboardResponse:
        payload = await get_or_load_account_dashboard(
            user_id,
            lambda: self._build_dashboard_payload(user_id),
        )
        return AccountDashboardResponse.model_validate(payload)

    async def update_profile(
        self, user_id: int, request: UpdateAccountRequest
    ) -> AccountProfileEnvelope:
        if request.total_capital is not None or request.currency is not None:
            await self.repository.upsert_account(user_id, request.total_capital, request.currency)

        await self.repository.update_user_profile(
            user_id=user_id,
            name=request.name,
            locale=request.locale,
            timezone_name=request.timezone,
        )
        self._schedule_dashboard_invalidation(user_id)
        self._schedule_profile_invalidation(user_id)
        return await self.get_profile(user_id, use_cache=False)
