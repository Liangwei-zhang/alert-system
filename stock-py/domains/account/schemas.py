from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UserProfileResponse(BaseModel):
    name: str | None = None
    email: str
    plan: str
    locale: str | None = None
    timezone: str | None = None


class AccountSummaryResponse(BaseModel):
    total_capital: float = 0
    currency: str = "USD"


class UpdateAccountRequest(BaseModel):
    name: str | None = Field(default=None, max_length=50)
    locale: str | None = None
    timezone: str | None = None
    total_capital: float | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, max_length=10)


class DashboardPortfolioItem(BaseModel):
    symbol: str
    shares: float
    avg_cost: float
    total_capital: float
    pct: float
    extra: dict[str, Any] | None = None


class DashboardWatchlistSummary(BaseModel):
    total: int
    notify_enabled: int


class SubscriptionChecklistResponse(BaseModel):
    has_capital: bool
    currency: str
    watchlist_count: int
    watchlist_notify_enabled: int
    portfolio_count: int
    push_device_count: int


class SubscriptionStateResponse(BaseModel):
    status: str
    started_at: str | None = None
    last_synced_at: str | None = None
    last_sync_reason: str | None = None
    checklist: SubscriptionChecklistResponse


class AccountDashboardDetailResponse(BaseModel):
    total_capital: float
    currency: str
    portfolio_value: float
    available_cash: float
    portfolio_pct: float


class AccountDashboardResponse(BaseModel):
    user: UserProfileResponse
    account: AccountDashboardDetailResponse
    portfolio: list[DashboardPortfolioItem]
    watchlist: DashboardWatchlistSummary
    subscription: SubscriptionStateResponse


class AccountProfileEnvelope(BaseModel):
    user: UserProfileResponse
    account: AccountSummaryResponse
