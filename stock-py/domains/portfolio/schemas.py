from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreatePortfolioRequest(BaseModel):
    symbol: str
    shares: int = Field(gt=0)
    avg_cost: float = Field(gt=0)
    target_profit: float = Field(default=0.15, ge=0.01, le=1)
    stop_loss: float = Field(default=0.08, ge=0.01, le=1)
    notify: bool = True
    notes: str | None = Field(default=None, max_length=200)


class UpdatePortfolioRequest(BaseModel):
    shares: int | None = Field(default=None, gt=0)
    avg_cost: float | None = Field(default=None, gt=0)
    target_profit: float | None = Field(default=None, ge=0.01, le=1)
    stop_loss: float | None = Field(default=None, ge=0.01, le=1)
    notify: bool | None = None
    notes: str | None = Field(default=None, max_length=200)


class PortfolioItemResponse(BaseModel):
    id: int
    symbol: str
    shares: int
    avg_cost: float
    total_capital: float
    target_profit: float
    stop_loss: float
    notify: bool
    notes: str | None = None
    extra: dict[str, Any] | None = None
    updated_at: datetime
