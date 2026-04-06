"""
Admin API endpoints for subscription management.
"""
from typing import List, Optional
from datetime import datetime, timedelta

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from infra.database import get_db
from domains.subscription.subscription_service import SubscriptionService
from domains.subscription.subscription import SubscriptionTier, SubscriptionStatus


router = APIRouter(prefix="/admin/subscriptions", tags=["admin-subscription"])


# Pydantic schemas
class SubscriptionCreate(BaseModel):
    user_id: int
    tier: SubscriptionTier = SubscriptionTier.FREE
    is_trial: bool = False
    trial_days: int = Field(default=14, ge=1, le=90)


class SubscriptionUpdate(BaseModel):
    tier: Optional[SubscriptionTier] = None
    status: Optional[SubscriptionStatus] = None
    signals_per_day: Optional[int] = Field(default=None, ge=-1)
    max_portfolios: Optional[int] = Field(default=None, ge=-1)
    max_strategies: Optional[int] = Field(default=None, ge=-1)
    realtime_signals: Optional[bool] = None
    backtesting: Optional[bool] = None
    api_access: Optional[bool] = None


class SubscriptionResponse(BaseModel):
    id: int
    user_id: int
    tier: SubscriptionTier
    status: SubscriptionStatus
    signals_per_day: int
    max_portfolios: int
    max_strategies: int
    realtime_signals: bool
    backtesting: bool
    api_access: bool
    is_trial: bool
    trial_ends_at: Optional[str]
    current_period_start: Optional[str]
    current_period_end: Optional[str]
    cancelled_at: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class SubscriptionStatsResponse(BaseModel):
    total: int
    active: int
    trial: int
    past_due: int
    expired: int
    cancelled: int
    by_tier: dict


def get_subscription_service(db: Session = Depends(get_db)) -> SubscriptionService:
    return SubscriptionService(db)


def _subscription_to_response(sub) -> SubscriptionResponse:
    """Convert subscription model to response."""
    return SubscriptionResponse(
        id=sub.id,
        user_id=sub.user_id,
        tier=sub.tier,
        status=sub.status,
        signals_per_day=sub.signals_per_day,
        max_portfolios=sub.max_portfolios,
        max_strategies=sub.max_strategies,
        realtime_signals=sub.realtime_signals,
        backtesting=sub.backtesting,
        api_access=sub.api_access,
        is_trial=sub.is_trial,
        trial_ends_at=sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
        current_period_start=sub.current_period_start.isoformat() if sub.current_period_start else None,
        current_period_end=sub.current_period_end.isoformat() if sub.current_period_end else None,
        cancelled_at=sub.cancelled_at.isoformat() if sub.cancelled_at else None,
        created_at=sub.created_at.isoformat(),
        updated_at=sub.updated_at.isoformat(),
    )


@router.get("", response_model=List[SubscriptionResponse])
def list_subscriptions(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    tier: Optional[str] = None,
    include_expired: bool = False,
    service: SubscriptionService = Depends(get_subscription_service),
):
    """List all subscriptions with optional filters."""
    status_filter = None
    if status:
        try:
            status_filter = SubscriptionStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}",
            )

    tier_filter = None
    if tier:
        try:
            tier_filter = SubscriptionTier(tier)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid tier: {tier}",
            )

    subscriptions = service.list_subscriptions(
        skip=skip,
        limit=limit,
        status=status_filter,
        tier=tier_filter,
        include_expired=include_expired,
    )
    return [_subscription_to_response(s) for s in subscriptions]


@router.get("/stats", response_model=SubscriptionStatsResponse)
def get_subscription_stats(
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Get subscription statistics."""
    stats = service.get_stats()
    return SubscriptionStatsResponse(**stats)


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
def get_subscription(
    subscription_id: int,
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Get subscription by ID."""
    sub = service.get_by_id(subscription_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )
    return _subscription_to_response(sub)


@router.get("/user/{user_id}", response_model=SubscriptionResponse)
def get_subscription_by_user(
    user_id: int,
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Get subscription by user ID."""
    sub = service.get_by_user_id(user_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found for user",
        )
    return _subscription_to_response(sub)


@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
def create_subscription(
    data: SubscriptionCreate,
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Create a new subscription."""
    try:
        sub = service.create_subscription(
            user_id=data.user_id,
            tier=data.tier,
            is_trial=data.is_trial,
            trial_days=data.trial_days,
        )
        return _subscription_to_response(sub)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch("/{subscription_id}", response_model=SubscriptionResponse)
def update_subscription(
    subscription_id: int,
    data: SubscriptionUpdate,
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Update a subscription."""
    sub = service.update_subscription(
        subscription_id=subscription_id,
        tier=data.tier,
        status=data.status,
        signals_per_day=data.signals_per_day,
        max_portfolios=data.max_portfolios,
        max_strategies=data.max_strategies,
        realtime_signals=data.realtime_signals,
        backtesting=data.backtesting,
        api_access=data.api_access,
    )
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )
    return _subscription_to_response(sub)


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subscription(
    subscription_id: int,
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Cancel a subscription (soft delete)."""
    if not service.delete_subscription(subscription_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )
    return None


# Status management endpoints
@router.post("/{subscription_id}/pause", response_model=SubscriptionResponse)
def pause_subscription(
    subscription_id: int,
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Pause an active subscription."""
    sub = service.pause_subscription(subscription_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot pause subscription (not active or not found)",
        )
    return _subscription_to_response(sub)


@router.post("/{subscription_id}/resume", response_model=SubscriptionResponse)
def resume_subscription(
    subscription_id: int,
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Resume a paused/cancelled subscription."""
    sub = service.resume_subscription(subscription_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot resume subscription (not paused or not found)",
        )
    return _subscription_to_response(sub)


@router.post("/{subscription_id}/expire", response_model=SubscriptionResponse)
def expire_subscription(
    subscription_id: int,
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Manually expire a subscription."""
    sub = service.expire_subscription(subscription_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )
    return _subscription_to_response(sub)


@router.post("/{subscription_id}/reactivate", response_model=SubscriptionResponse)
def reactivate_subscription(
    subscription_id: int,
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Reactivate an expired or cancelled subscription."""
    sub = service.reactivate_subscription(subscription_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reactivate subscription (not found)",
        )
    return _subscription_to_response(sub)


# Renewal endpoints
@router.post("/{subscription_id}/renew", response_model=SubscriptionResponse)
def renew_subscription(
    subscription_id: int,
    days: int = 30,
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Manually trigger renewal for a subscription."""
    new_period_end = datetime.utcnow() + timedelta(days=days)
    sub = service.handle_renewal(subscription_id, new_period_end)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot renew subscription (cancelled/expired or not found)",
        )
    return _subscription_to_response(sub)


@router.post("/check-expired")
def check_expired_subscriptions(
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Check and process expired subscriptions."""
    expired = service.check_and_process_expired()
    return {
        "processed": len(expired),
        "subscriptions": [_subscription_to_response(s) for s in expired],
    }


@router.get("/trials/expiring")
def get_expiring_trials(
    days: int = 3,
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Get trials expiring within specified days."""
    trials = service.check_trials_expiring(days=days)
    return {
        "count": len(trials),
        "trials": [_subscription_to_response(s) for s in trials],
    }