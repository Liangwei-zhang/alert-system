from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateWatchlistRequest(BaseModel):
    symbol: str
    notify: bool = True
    min_score: int = Field(default=65, ge=0, le=100)


class UpdateWatchlistRequest(BaseModel):
    notify: bool | None = None
    min_score: int | None = Field(default=None, ge=0, le=100)


class WatchlistItemResponse(BaseModel):
    id: int
    symbol: str
    notify: bool
    min_score: int
    created_at: datetime
