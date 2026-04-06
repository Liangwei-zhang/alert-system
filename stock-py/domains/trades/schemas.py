"""
Pydantic schemas for trades domain.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class AdjustTradeRequest(BaseModel):
    """Schema for adjusting actual shares/price in a trade."""

    actual_shares: float = Field(..., gt=0, description="Actual number of shares executed")
    actual_price: float = Field(..., gt=0, description="Actual price per share")

    @field_validator("actual_shares", "actual_price")
    @classmethod
    def validate_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Value must be positive")
        return v


class TradeInfoResponse(BaseModel):
    """Schema for trade info response."""

    id: str
    symbol: str
    action: str
    suggested_shares: float
    suggested_price: float
    suggested_amount: float
    status: str

    model_config = None


class TradeInfoPublicResponse(BaseModel):
    """Schema for public trade info (link-based)."""

    trade: TradeInfoResponse
    is_expired: bool
    expires_at: datetime


class TradeInfoAppResponse(BaseModel):
    """Schema for app trade info (authenticated)."""

    trade: TradeInfoResponse
    is_expired: bool
    expires_at: datetime


class ConfirmResponse(BaseModel):
    """Schema for confirm response."""

    message: str


class IgnoreResponse(BaseModel):
    """Schema for ignore response."""

    message: str


class AdjustResponse(BaseModel):
    """Schema for adjust response."""

    message: str
    actual_amount: float


class TradeConfirmQuery(BaseModel):
    """Query parameters for trade confirmation."""

    action: str = Field(..., pattern="^(accept|ignore)$")
    t: str = Field(..., min_length=1, description="Link token")


class TradeInfoQuery(BaseModel):
    """Query parameters for trade info."""

    t: str = Field(..., min_length=1, description="Link token")
