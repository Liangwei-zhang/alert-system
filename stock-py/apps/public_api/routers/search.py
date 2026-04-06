from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from domains.search.repository import SearchRepository
from domains.search.schemas import SearchSymbolsResponse
from domains.search.service import SearchService
from infra.db.session import get_db_session

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/symbols", response_model=SearchSymbolsResponse)
async def search_symbols(
    q: str = Query(..., min_length=1, max_length=50),
    type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_db_session),
) -> SearchSymbolsResponse:
    service = SearchService(SearchRepository(session))
    return await service.search_symbols(q=q, limit=limit, asset_type=type or None)
