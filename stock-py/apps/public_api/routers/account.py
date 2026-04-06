from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from domains.account.repository import AccountRepository
from domains.account.schemas import (
    AccountDashboardResponse,
    AccountProfileEnvelope,
    UpdateAccountRequest,
)
from domains.account.service import AccountService
from domains.auth.repository import UserRepository
from domains.portfolio.repository import PortfolioRepository
from domains.subscription.repository import SubscriptionRepository
from domains.subscription.schemas import StartSubscriptionRequest, StartSubscriptionResponse
from domains.subscription.service import StartSubscriptionService
from domains.watchlist.repository import WatchlistRepository
from infra.db.session import get_db_session
from infra.security.auth import CurrentUser, require_user

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/profile", response_model=AccountProfileEnvelope)
async def get_profile(
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> AccountProfileEnvelope:
    service = AccountService(AccountRepository(session))
    return await service.get_profile(current_user.user_id)


@router.get("/dashboard", response_model=AccountDashboardResponse)
async def get_dashboard(
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> AccountDashboardResponse:
    service = AccountService(AccountRepository(session))
    return await service.get_dashboard(current_user.user_id)


@router.put("/profile", response_model=AccountProfileEnvelope)
async def update_profile(
    data: UpdateAccountRequest,
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> AccountProfileEnvelope:
    service = AccountService(AccountRepository(session))
    return await service.update_profile(current_user.user_id, data)


@router.post("/start-subscription", response_model=StartSubscriptionResponse)
async def start_subscription(
    data: StartSubscriptionRequest,
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> StartSubscriptionResponse:
    service = StartSubscriptionService(
        user_repository=UserRepository(session),
        account_repository=AccountRepository(session),
        subscription_repository=SubscriptionRepository(session),
        watchlist_repository=WatchlistRepository(session),
        portfolio_repository=PortfolioRepository(session),
    )
    return await service.start_subscription(current_user.user_id, data)
