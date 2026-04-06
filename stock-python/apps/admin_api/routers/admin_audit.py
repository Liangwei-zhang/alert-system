"""
Admin audit log API endpoints.
"""
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from infra.database import async_session_maker, get_db
from domains.admin.audit import AuditLog, AuditAction


router = APIRouter(prefix="/admin/audit", tags=["admin-audit"])


# ============== Pydantic Schemas ==============

class AuditLogResponse(BaseModel):
    id: int
    admin_user_id: Optional[int]
    username: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class AuditLogCreate(BaseModel):
    admin_user_id: int
    username: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str = "success"
    error_message: Optional[str] = None


class AuditLogFilter(BaseModel):
    admin_user_id: Optional[int] = None
    username: Optional[str] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class AuditStatsResponse(BaseModel):
    total_logs: int
    by_action: dict
    by_status: dict
    by_user: dict
    recent_activity: List[AuditLogResponse]


# ============== Dependency ==============

async def get_async_db() -> AsyncSession:
    """Get async database session."""
    async with async_session_maker() as session:
        yield session


# ============== Endpoints ==============

@router.get("", response_model=List[AuditLogResponse])
async def list_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    admin_user_id: Optional[int] = None,
    username: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_async_db),
):
    """
    List audit logs with optional filtering.
    """
    query = select(AuditLog)

    # Build filters
    filters = []
    if admin_user_id:
        filters.append(AuditLog.admin_user_id == admin_user_id)
    if username:
        filters.append(AuditLog.username.ilike(f"%{username}%"))
    if action:
        filters.append(AuditLog.action == action)
    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)
    if resource_id:
        filters.append(AuditLog.resource_id == resource_id)
    if status:
        filters.append(AuditLog.status == status)
    if start_date:
        filters.append(AuditLog.created_at >= start_date)
    if end_date:
        filters.append(AuditLog.created_at <= end_date)

    if filters:
        query = query.where(and_(*filters))

    # Order by most recent first
    query = query.order_by(desc(AuditLog.created_at)).offset(skip).limit(limit)

    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        AuditLogResponse(
            id=log.id,
            admin_user_id=log.admin_user_id,
            username=log.username,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details=log.details,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            status=log.status,
            error_message=log.error_message,
            created_at=log.created_at.isoformat(),
        )
        for log in logs
    ]


@router.get("/stats", response_model=AuditStatsResponse)
async def get_audit_stats(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get audit log statistics for the specified number of days.
    """
    start_date = datetime.utcnow() - timedelta(days=days)

    # Get all logs in date range
    query = select(AuditLog).where(AuditLog.created_at >= start_date)
    result = await db.execute(query)
    logs = result.scalars().all()

    # Calculate stats
    total_logs = len(logs)
    by_action = {}
    by_status = {}
    by_user = {}

    for log in logs:
        # By action
        by_action[log.action] = by_action.get(log.action, 0) + 1
        # By status
        by_status[log.status] = by_status.get(log.status, 0) + 1
        # By user
        if log.username:
            by_user[log.username] = by_user.get(log.username, 0) + 1

    # Get recent activity (last 10)
    recent_query = (
        select(AuditLog)
        .order_by(desc(AuditLog.created_at))
        .limit(10)
    )
    result = await db.execute(recent_query)
    recent_logs = result.scalars().all()

    return AuditStatsResponse(
        total_logs=total_logs,
        by_action=by_action,
        by_status=by_status,
        by_user=by_user,
        recent_activity=[
            AuditLogResponse(
                id=log.id,
                admin_user_id=log.admin_user_id,
                username=log.username,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                details=log.details,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                status=log.status,
                error_message=log.error_message,
                created_at=log.created_at.isoformat(),
            )
            for log in recent_logs
        ],
    )


@router.get("/actions")
async def list_audit_actions(
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all available audit action types.
    """
    return {
        "actions": [
            {"value": action.value, "description": action.name.replace("_", " ").title()}
            for action in AuditAction
        ]
    }


@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: int,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get a specific audit log entry by ID.
    """
    query = select(AuditLog).where(AuditLog.id == log_id)
    result = await db.execute(query)
    log = result.scalar_one_or_none()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log not found"
        )

    return AuditLogResponse(
        id=log.id,
        admin_user_id=log.admin_user_id,
        username=log.username,
        action=log.action,
        resource_type=log.resource_type,
        resource_id=log.resource_id,
        details=log.details,
        ip_address=log.ip_address,
        user_agent=log.user_agent,
        status=log.status,
        error_message=log.error_message,
        created_at=log.created_at.isoformat(),
    )


@router.post("", response_model=AuditLogResponse, status_code=status.HTTP_201_CREATED)
async def create_audit_log(
    data: AuditLogCreate,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create a new audit log entry (manual logging).
    """
    log = AuditLog(
        admin_user_id=data.admin_user_id,
        username=data.username,
        action=data.action,
        resource_type=data.resource_type,
        resource_id=data.resource_id,
        details=data.details,
        ip_address=data.ip_address,
        user_agent=data.user_agent,
        status=data.status,
        error_message=data.error_message,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    return AuditLogResponse(
        id=log.id,
        admin_user_id=log.admin_user_id,
        username=log.username,
        action=log.action,
        resource_type=log.resource_type,
        resource_id=log.resource_id,
        details=log.details,
        ip_address=log.ip_address,
        user_agent=log.user_agent,
        status=log.status,
        error_message=log.error_message,
        created_at=log.created_at.isoformat(),
    )


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_audit_log(
    log_id: int,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Delete an audit log entry.
    """
    query = select(AuditLog).where(AuditLog.id == log_id)
    result = await db.execute(query)
    log = result.scalar_one_or_none()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log not found"
        )

    await db.delete(log)
    await db.commit()
    return None