from __future__ import annotations

from infra.core.errors import AppError

PORTFOLIO_LIMITS = {"free": 3, "pro": 6, "max": 12, "premium": 12}


class PortfolioPolicy:
    def normalize_symbol(self, symbol: str) -> str:
        normalized = symbol.strip().upper()
        if not normalized:
            raise AppError("invalid_symbol", "Symbol is required", status_code=400)
        return normalized

    def validate_numbers(self, shares: int, avg_cost: float) -> None:
        if shares <= 0:
            raise AppError("invalid_shares", "Shares must be greater than 0", status_code=400)
        if avg_cost <= 0:
            raise AppError(
                "invalid_avg_cost", "Average cost must be greater than 0", status_code=400
            )

    def enforce_plan_limit(self, plan: str, current_count: int) -> None:
        limit = PORTFOLIO_LIMITS.get(plan, 3)
        if current_count >= limit:
            raise AppError(
                "portfolio_limit", f"Portfolio limit reached ({limit} positions)", status_code=400
            )
