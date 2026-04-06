from __future__ import annotations

from pydantic import BaseModel, Field


class StartSubscriptionAccountRequest(BaseModel):
    total_capital: float = Field(gt=0)
    currency: str = Field(min_length=3, max_length=10)


class StartSubscriptionWatchlistItem(BaseModel):
    symbol: str
    min_score: int = Field(default=65, ge=0, le=100)
    notify: bool = True


class StartSubscriptionPortfolioItem(BaseModel):
    symbol: str
    shares: int = Field(gt=0)
    avg_cost: float = Field(gt=0)
    target_profit: float = Field(default=0.15, ge=0.01, le=1)
    stop_loss: float = Field(default=0.08, ge=0.01, le=1)
    notify: bool = True
    notes: str | None = Field(default=None, max_length=200)


class StartSubscriptionRequest(BaseModel):
    allow_empty_portfolio: bool = False
    account: StartSubscriptionAccountRequest | None = None
    watchlist: list[StartSubscriptionWatchlistItem] | None = None
    portfolio: list[StartSubscriptionPortfolioItem] | None = None


class StartSubscriptionResponse(BaseModel):
    message: str
    subscription: dict
