from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from domains.portfolio.repository import PortfolioRepository
from domains.portfolio.schemas import (
    CreatePortfolioRequest,
    PortfolioItemResponse,
    UpdatePortfolioRequest,
)
from domains.portfolio.service import PortfolioService
from infra.db.session import get_db_session
from infra.security.auth import CurrentUser, require_user

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("", response_model=list[PortfolioItemResponse])
async def list_portfolio(
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[PortfolioItemResponse]:
    service = PortfolioService(PortfolioRepository(session))
    return await service.list_positions(current_user.user_id)


@router.post("", response_model=PortfolioItemResponse, status_code=status.HTTP_201_CREATED)
async def create_position(
    data: CreatePortfolioRequest,
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> PortfolioItemResponse:
    service = PortfolioService(PortfolioRepository(session))
    return await service.add_position(current_user.user_id, current_user.plan, data)


@router.put("/{item_id}", response_model=PortfolioItemResponse)
async def update_position(
    item_id: int,
    data: UpdatePortfolioRequest,
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> PortfolioItemResponse:
    service = PortfolioService(PortfolioRepository(session))
    return await service.update_position(current_user.user_id, item_id, data)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_position(
    item_id: int,
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    service = PortfolioService(PortfolioRepository(session))
    await service.delete_position(current_user.user_id, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
