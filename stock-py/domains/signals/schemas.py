from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class DesktopSignalAlert(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    type: str = Field(pattern="^(buy|sell|split_buy|split_sell)$")
    score: float = Field(ge=0, le=100)
    price: float = Field(gt=0)
    reasons: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=100)
    probability: float | None = Field(default=None, ge=0, le=1)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit_1: float | None = Field(default=None, gt=0)
    take_profit_2: float | None = Field(default=None, gt=0)
    take_profit_3: float | None = Field(default=None, gt=0)
    strategy_window: str | None = Field(default=None, max_length=50)
    market_regime: str | None = Field(default=None, max_length=50)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()


class DesktopSignalRequest(BaseModel):
    source: str = Field(min_length=1, max_length=50)
    emitted_at: datetime
    alert: DesktopSignalAlert
    analysis: dict[str, Any] = Field(default_factory=dict)


class SignalCandidate(BaseModel):
    symbol: str
    type: str
    score: float
    price: float
    reasons: list[str] = Field(default_factory=list)
    analysis: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0, le=100)
    probability: float | None = Field(default=None, ge=0, le=1)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit_1: float | None = Field(default=None, gt=0)
    take_profit_2: float | None = Field(default=None, gt=0)
    take_profit_3: float | None = Field(default=None, gt=0)
    strategy_window: str | None = Field(default=None, max_length=50)
    market_regime: str | None = Field(default=None, max_length=50)


class ScannerBucketItem(BaseModel):
    bucket_id: int = Field(ge=0)
    symbol: str
    priority: int = Field(ge=0)


class DesktopSignalIngestResponse(BaseModel):
    signal_id: int
    dedupe_key: str
    suppressed: bool
    queued_recipient_count: int = 0
    status: str
