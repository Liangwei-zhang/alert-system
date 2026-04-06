from __future__ import annotations

from domains.account.repository import AccountRepository
from domains.auth.repository import UserRepository
from domains.portfolio.repository import PortfolioRepository
from domains.subscription.policies import SubscriptionPolicy
from domains.subscription.repository import SubscriptionRepository
from domains.subscription.schemas import StartSubscriptionRequest, StartSubscriptionResponse
from domains.watchlist.repository import WatchlistRepository
from infra.cache.account_dashboard_cache import schedule_invalidate_account_dashboard
from infra.cache.account_profile_cache import schedule_invalidate_account_profile
from infra.core.errors import AppError
from infra.events.outbox import OutboxPublisher


class StartSubscriptionService:
    def __init__(
        self,
        user_repository: UserRepository,
        account_repository: AccountRepository,
        subscription_repository: SubscriptionRepository,
        watchlist_repository: WatchlistRepository,
        portfolio_repository: PortfolioRepository,
    ) -> None:
        self.user_repository = user_repository
        self.account_repository = account_repository
        self.subscription_repository = subscription_repository
        self.watchlist_repository = watchlist_repository
        self.portfolio_repository = portfolio_repository
        self.policy = SubscriptionPolicy()
        self.outbox = OutboxPublisher(self.subscription_repository.session)

    async def start_subscription(
        self,
        user_id: int,
        request: StartSubscriptionRequest,
    ) -> StartSubscriptionResponse:
        user = await self.user_repository.get_by_id(user_id)
        if user is None:
            raise AppError("user_not_found", "User not found", status_code=404)

        if request.account is not None:
            await self.account_repository.upsert_account(
                user_id=user_id,
                total_capital=request.account.total_capital,
                currency=request.account.currency,
            )

        if request.watchlist is not None:
            await self.watchlist_repository.replace_all(
                user_id,
                [item.model_dump() for item in request.watchlist],
            )
            await self.outbox.publish_after_commit(
                topic="watchlist.changed",
                key=str(user_id),
                payload={"user_id": user_id, "action": "replace_all"},
            )

        if request.portfolio is not None:
            await self.portfolio_repository.replace_all(
                user_id,
                [item.model_dump() for item in request.portfolio],
            )
            await self.outbox.publish_after_commit(
                topic="portfolio.changed",
                key=str(user_id),
                payload={"user_id": user_id, "action": "replace_all"},
            )

        dashboard = await self.account_repository.get_dashboard(user_id)
        account = dashboard["account"]
        watchlist_items = dashboard["watchlist"]
        portfolio_items = dashboard["portfolio"]

        total_capital = float(account.total_capital) if account else 0
        currency = account.currency if account else "USD"
        summary = {
            "watchlist_count": len(watchlist_items),
            "watchlist_notify_enabled": sum(1 for item in watchlist_items if item.notify),
            "portfolio_count": len(portfolio_items),
            "push_device_count": 0,
        }

        self.policy.validate_start_request(
            total_capital=total_capital,
            watchlist_count=summary["watchlist_count"],
            portfolio_count=summary["portfolio_count"],
            allow_empty_portfolio=request.allow_empty_portfolio,
        )
        self.policy.enforce_watchlist_limit(user.plan, summary["watchlist_count"])
        self.policy.enforce_portfolio_limit(user.plan, summary["portfolio_count"])

        current_watchlist_snapshot = [
            {
                "symbol": item.symbol,
                "notify": item.notify,
                "min_score": item.min_score,
            }
            for item in watchlist_items
        ]
        current_portfolio_snapshot = [
            {
                "symbol": item.symbol,
                "shares": item.shares,
                "avg_cost": float(item.avg_cost),
                "total_capital": float(item.total_capital),
                "target_profit": float(item.target_profit),
                "stop_loss": float(item.stop_loss),
                "notify": item.notify,
                "notes": item.notes,
            }
            for item in portfolio_items
        ]

        snapshot = {
            "total_capital": total_capital,
            "currency": currency,
            "watchlist": (
                [item.model_dump() for item in request.watchlist]
                if request.watchlist is not None
                else current_watchlist_snapshot
            ),
            "portfolio": (
                [item.model_dump() for item in request.portfolio]
                if request.portfolio is not None
                else current_portfolio_snapshot
            ),
            "allow_empty_portfolio": request.allow_empty_portfolio,
        }

        next_extra = self.policy.build_state(
            user.extra if isinstance(user.extra, dict) else {}, snapshot, summary
        )
        await self.subscription_repository.save_snapshot(user_id, snapshot)
        await self.subscription_repository.update_user_subscription_extra(user_id, next_extra)
        await self.outbox.publish_after_commit(
            topic="account.subscription.started",
            key=str(user_id),
            payload={
                "user_id": user_id,
                "status": "active",
                "summary": summary,
            },
        )
        schedule_invalidate_account_dashboard(
            getattr(self.subscription_repository, "session", None),
            user_id,
        )
        if request.account is not None:
            schedule_invalidate_account_profile(
                getattr(self.subscription_repository, "session", None),
                user_id,
            )

        return StartSubscriptionResponse(
            message="訂閱已開始，監控快照已同步",
            subscription=next_extra["subscription"],
        )
