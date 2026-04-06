from __future__ import annotations

from infra.core.errors import AppError

WATCHLIST_LIMITS = {"free": 5, "pro": 10, "max": 20, "premium": 20}


class WatchlistPolicy:
    def normalize_symbol(self, symbol: str) -> str:
        normalized = symbol.strip().upper()
        if not normalized:
            raise AppError("invalid_symbol", "Symbol is required", status_code=400)
        return normalized

    def validate_min_score(self, min_score: int) -> None:
        if not 0 <= min_score <= 100:
            raise AppError(
                "invalid_min_score", "min_score must be between 0 and 100", status_code=400
            )

    def enforce_plan_limit(self, plan: str, current_count: int) -> None:
        limit = WATCHLIST_LIMITS.get(plan, 10)
        if current_count >= limit:
            raise AppError(
                "watchlist_limit", f"Watchlist limit reached ({limit} symbols)", status_code=400
            )
