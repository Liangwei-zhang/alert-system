from __future__ import annotations

from pydantic import BaseModel, Field


class SearchSymbolsQuery(BaseModel):
    q: str = Field(min_length=1, max_length=50)
    type: str | None = None
    limit: int = Field(default=20, ge=1, le=50)
    cursor: str | None = None


class SearchSymbolItem(BaseModel):
    symbol: str
    name: str | None = None
    name_zh: str | None = None
    asset_type: str | None = None
    exchange: str | None = None
    sector: str | None = None


class SearchSymbolsResponse(BaseModel):
    items: list[SearchSymbolItem]
    query: str
