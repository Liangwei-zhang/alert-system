"""
Admin stats API endpoints for system monitoring and subscriptions.
"""
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from infra.database import get_db
from domains.admin.admin_service import AdminService
from domains.admin.admin_stats_service import AdminStatsService
from domains.subscription.subscription import SubscriptionTier, SubscriptionStatus


router = APIRouter(prefix="/admin", tags=["admin-stats"])


# ============== Response Models ==============

class SystemStatsResponse(BaseModel):
    users: dict
    signals: dict
    stocks: dict
    portfolios: dict
    strategies: dict
    timestamp: str


class SubscriptionStatsResponse(BaseModel):
    total: int
    active: int
    trial: int
    past_due: int
    by_tier: dict


class SubscriptionResponse(BaseModel):
    id: int
    user_id: int
    tier: str
    status: str
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
    created_at: str

    class Config:
        from_attributes = True


class SubscriptionUpdateRequest(BaseModel):
    tier: Optional[str] = None
    status: Optional[str] = None
    signals_per_day: Optional[int] = None
    max_portfolios: Optional[int] = None
    max_strategies: Optional[int] = None
    realtime_signals: Optional[bool] = None
    backtesting: Optional[bool] = None
    api_access: Optional[bool] = None


class TaskStatusResponse(BaseModel):
    total: int
    active_workers: int
    queued: int
    started: int
    succeeded: int
    failed: int
    tasks: List[dict]


class CeleryStatusResponse(BaseModel):
    status: str
    active_workers: int
    worker_list: List[str]
    active_tasks: int
    queued_tasks: int
    reserved_tasks: int
    tasks: List[dict]
    workers_detail: dict
    error: Optional[str] = None


class SystemHealthResponse(BaseModel):
    platform: str
    platform_version: str
    python_version: str
    cpu: dict
    memory: dict
    disk: dict
    network: dict
    process: dict
    status: str
    error: Optional[str] = None


class OperationalStatsResponse(BaseModel):
    users: dict
    subscriptions: dict
    signals: dict
    signals_distribution: dict
    celery: dict
    system_health: dict
    stocks: dict
    portfolios: dict
    strategies: dict
    notifications: dict
    timestamp: str


# ============== Dependencies ==============

def get_admin_service(db: Session = Depends(get_db)) -> AdminService:
    return AdminService(db)


def get_admin_stats_service(db: Session = Depends(get_db)) -> AdminStatsService:
    return AdminStatsService(db)


# ============== Endpoints ==============

@router.get("/stats", response_model=SystemStatsResponse)
def get_system_stats(
    service: AdminService = Depends(get_admin_service),
):
    """
    Get system statistics including user count, signal count, etc.
    """
    stats = service.get_system_stats()
    return SystemStatsResponse(**stats)


@router.get("/subscription-stats", response_model=SubscriptionStatsResponse)
def get_subscription_stats(
    service: AdminService = Depends(get_admin_service),
):
    """
    Get subscription statistics by tier and status.
    """
    stats = service.get_subscription_stats()
    return SubscriptionStatsResponse(**stats)


@router.get("/subscriptions", response_model=List[SubscriptionResponse])
def list_subscriptions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[str] = None,
    tier: Optional[str] = None,
    service: AdminService = Depends(get_admin_service),
):
    """
    List all subscriptions with optional filtering.
    """
    status_enum = None
    if status:
        try:
            status_enum = SubscriptionStatus(status)
        except ValueError:
            pass

    tier_enum = None
    if tier:
        try:
            tier_enum = SubscriptionTier(tier)
        except ValueError:
            pass

    subs = service.list_subscriptions(
        skip=skip,
        limit=limit,
        status=status_enum,
        tier=tier_enum,
    )

    return [
        SubscriptionResponse(
            id=s.id,
            user_id=s.user_id,
            tier=s.tier.value,
            status=s.status.value,
            signals_per_day=s.signals_per_day,
            max_portfolios=s.max_portfolios,
            max_strategies=s.max_strategies,
            realtime_signals=s.realtime_signals,
            backtesting=s.backtesting,
            api_access=s.api_access,
            is_trial=s.is_trial,
            trial_ends_at=s.trial_ends_at.isoformat() if s.trial_ends_at else None,
            current_period_start=s.current_period_start.isoformat() if s.current_period_start else None,
            current_period_end=s.current_period_end.isoformat() if s.current_period_end else None,
            created_at=s.created_at.isoformat(),
        )
        for s in subs
    ]


@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
def get_subscription(
    subscription_id: int,
    service: AdminService = Depends(get_admin_service),
):
    """
    Get a specific subscription by ID.
    """
    sub = service.get_subscription_by_id(subscription_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    return SubscriptionResponse(
        id=sub.id,
        user_id=sub.user_id,
        tier=sub.tier.value,
        status=sub.status.value,
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
        created_at=sub.created_at.isoformat(),
    )


@router.patch("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
def update_subscription(
    subscription_id: int,
    data: SubscriptionUpdateRequest,
    service: AdminService = Depends(get_admin_service),
):
    """
    Update a subscription (change tier, status, features).
    """
    # Validate tier if provided
    tier_enum = None
    if data.tier:
        try:
            tier_enum = SubscriptionTier(data.tier)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid tier. Valid values: {[t.value for t in SubscriptionTier]}"
            )

    # Validate status if provided
    status_enum = None
    if data.status:
        try:
            status_enum = SubscriptionStatus(data.status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Valid values: {[s.value for s in SubscriptionStatus]}"
            )

    sub = service.update_subscription(
        subscription_id=subscription_id,
        tier=tier_enum,
        status=status_enum,
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
            detail="Subscription not found"
        )

    return SubscriptionResponse(
        id=sub.id,
        user_id=sub.user_id,
        tier=sub.tier.value,
        status=sub.status.value,
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
        created_at=sub.created_at.isoformat(),
    )


@router.get("/tasks", response_model=TaskStatusResponse)
def get_task_status(
    service: AdminService = Depends(get_admin_service),
):
    """
    Get Celery task queue status.
    Requires celery-inspect library or direct Redis inspection.
    """
    # Try to import celery inspection (requires celery-inspect or flower)
    try:
        from celery import current_app
        inspector = current_app.control.inspect()
        
        # Get active workers
        active_workers = list(inspector.active().keys()) if inspector.active() else []
        
        # Get stats
        stats = inspector.stats() or {}
        
        # Get scheduled tasks
        scheduled = inspector.scheduled() or []
        
        # Get active tasks
        active = inspector.active() or {}
        
        # Build task list
        tasks = []
        for worker, worker_tasks in active.items():
            for t in worker_tasks:
                tasks.append({
                    "id": t.get("id"),
                    "name": t.get("name"),
                    "worker": worker,
                    "status": "started",
                    "started_at": t.get("time_start"),
                })
        
        return TaskStatusResponse(
            total=len(tasks),
            active_workers=len(active_workers),
            queued=len(scheduled),
            started=len(tasks),
            succeeded=0,
            failed=0,
            tasks=tasks,
        )
    except Exception as e:
        # Fallback: return basic info from Redis directly
        try:
            import redis
            from infra.config import settings
            
            r = redis.from_url(settings.REDIS_URL)
            
            # Get Celery keys
            keys = r.keys("celery*")
            
            return TaskStatusResponse(
                total=0,
                active_workers=0,
                queued=0,
                started=0,
                succeeded=0,
                failed=0,
                tasks=[],
                _note=f"Could not inspect Celery: {str(e)}",
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Task inspection unavailable"
            )

# ============== New Admin Stats Endpoints ==============

@router.get("/operational-stats", response_model=OperationalStatsResponse)
def get_operational_stats(
    service: AdminStatsService = Depends(get_admin_stats_service),
):
    """
    Get comprehensive operational statistics.
    Includes users, subscriptions, signals, celery tasks, and system health.
    """
    stats = service.get_comprehensive_stats()
    return OperationalStatsResponse(**stats)


@router.get("/users-stats")
def get_user_stats(
    service: AdminStatsService = Depends(get_admin_stats_service),
):
    """Get user statistics."""
    return service.get_user_stats()


@router.get("/signals-stats")
def get_signal_stats(
    service: AdminStatsService = Depends(get_admin_stats_service),
):
    """Get signal statistics."""
    return service.get_signal_stats()


@router.get("/signals-distribution")
def get_signal_distribution(
    service: AdminStatsService = Depends(get_admin_stats_service),
):
    """Get signal distribution by type, direction, and source."""
    return service.get_signal_distribution_stats()


@router.get("/celery-status", response_model=CeleryStatusResponse)
def get_celery_status(
    service: AdminStatsService = Depends(get_admin_stats_service),
):
    """Get Celery task queue status."""
    status = service.get_celery_status()
    return CeleryStatusResponse(**status)


@router.get("/system-health", response_model=SystemHealthResponse)
def get_system_health(
    service: AdminStatsService = Depends(get_admin_stats_service),
):
    """Get system health metrics (CPU, memory, disk, network)."""
    health = service.get_system_health()
    return SystemHealthResponse(**health)
