from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from infra.core.errors import AppError

WATCHLIST_LIMITS = {"free": 5, "pro": 10, "max": 20, "premium": 20}
PORTFOLIO_LIMITS = {"free": 3, "pro": 6, "max": 12, "premium": 12}


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SubscriptionPolicy:
    def build_state(
        self,
        extra: dict[str, Any] | None,
        snapshot: dict[str, Any],
        summary: dict[str, int],
    ) -> dict[str, Any]:
        current_extra = extra if isinstance(extra, dict) else {}
        subscription = (
            current_extra.get("subscription")
            if isinstance(current_extra.get("subscription"), dict)
            else {}
        )
        started_at = (
            subscription.get("started_at")
            if isinstance(subscription.get("started_at"), str)
            else utcnow_iso()
        )
        return {
            **current_extra,
            "subscription": {
                **subscription,
                "status": "active",
                "started_at": started_at,
                "last_synced_at": utcnow_iso(),
                "last_sync_reason": "manual-start",
                "snapshot": {
                    **snapshot,
                    "watchlist_count": summary["watchlist_count"],
                    "watchlist_notify_enabled": summary["watchlist_notify_enabled"],
                    "portfolio_count": summary["portfolio_count"],
                    "push_device_count": summary["push_device_count"],
                },
            },
        }

    def validate_start_request(
        self,
        total_capital: float,
        watchlist_count: int,
        portfolio_count: int,
        allow_empty_portfolio: bool,
    ) -> None:
        if total_capital <= 0:
            raise AppError("missing_capital", "請先設定總資金，再開始訂閱", status_code=400)
        if watchlist_count <= 0:
            raise AppError(
                "missing_watchlist", "請至少新增一個關注標的，再開始訂閱", status_code=400
            )
        if portfolio_count <= 0 and not allow_empty_portfolio:
            raise AppError(
                "missing_portfolio",
                "目前尚未填入持倉，如確認空倉請以 allow_empty_portfolio 重新提交",
                status_code=400,
            )

    def enforce_watchlist_limit(self, plan: str, watchlist_count: int) -> None:
        limit = WATCHLIST_LIMITS.get(plan, 10)
        if watchlist_count > limit:
            raise AppError(
                "watchlist_limit", f"Watchlist limit reached ({limit} symbols)", status_code=400
            )

    def enforce_portfolio_limit(self, plan: str, portfolio_count: int) -> None:
        limit = PORTFOLIO_LIMITS.get(plan, 3)
        if portfolio_count > limit:
            raise AppError(
                "portfolio_limit", f"Portfolio limit reached ({limit} positions)", status_code=400
            )
