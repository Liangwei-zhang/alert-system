from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from domains.watchlist.repository import WatchlistRepository
from domains.watchlist.schemas import (
    CreateWatchlistRequest,
    UpdateWatchlistRequest,
    WatchlistItemResponse,
)
from domains.watchlist.service import WatchlistService
from infra.db.session import get_db_session
from infra.security.auth import CurrentUser, require_user

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("", response_model=list[WatchlistItemResponse])
async def list_watchlist(
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[WatchlistItemResponse]:
    service = WatchlistService(WatchlistRepository(session))
    return await service.list_items(current_user.user_id)


@router.post("", response_model=WatchlistItemResponse, status_code=status.HTTP_201_CREATED)
async def create_watchlist_item(
    data: CreateWatchlistRequest,
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> WatchlistItemResponse:
    service = WatchlistService(WatchlistRepository(session))
    return await service.add_item(current_user.user_id, current_user.plan, data)


@router.put("/{item_id}", response_model=WatchlistItemResponse)
async def update_watchlist_item(
    item_id: int,
    data: UpdateWatchlistRequest,
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> WatchlistItemResponse:
    service = WatchlistService(WatchlistRepository(session))
    return await service.update_item(current_user.user_id, item_id, data)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist_item(
    item_id: int,
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    service = WatchlistService(WatchlistRepository(session))
    await service.delete_item(current_user.user_id, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
