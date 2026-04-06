"""
Notification API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from infra.database import get_db
from infra.security import get_current_user
from domains.auth.user import User
from domains.notifications.notification import (
    NotificationResponse,
    NotificationListResponse,
    NotificationCreate,
    DeviceCreate,
    DeviceResponse,
    MarkReadRequest,
)
from apps.workers.notification_orchestrator.notification_service import NotificationService, notification_broadcaster

router = APIRouter(prefix="", tags=["notifications"])


@router.get("/notifications", response_model=NotificationListResponse)
async def get_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user notifications."""
    service = NotificationService(db)
    notifications, total = await service.get_user_notifications(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        unread_only=unread_only,
    )
    unread_count = await service.get_unread_count(current_user.id)
    
    return NotificationListResponse(
        notifications=[NotificationResponse.from_orm(n) for n in notifications],
        total=total,
        unread_count=unread_count,
    )


@router.get("/notifications/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get count of unread notifications."""
    service = NotificationService(db)
    count = await service.get_unread_count(current_user.id)
    return {"unread_count": count}


@router.post("/notifications/mark-read")
async def mark_notifications_read(
    request: MarkReadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark notifications as read."""
    service = NotificationService(db)
    updated = await service.mark_as_read(request.notification_ids, current_user.id)
    return {"updated": updated}


@router.post("/notifications/mark-all-read")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all notifications as read."""
    service = NotificationService(db)
    updated = await service.mark_all_as_read(current_user.id)
    return {"updated": updated}


@router.delete("/notifications/{notification_id}")
async def delete_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a notification."""
    service = NotificationService(db)
    deleted = await service.delete_notification(notification_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"deleted": True}


# Device registration endpoints
@router.get("/devices", response_model=list[DeviceResponse])
async def get_devices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's registered devices."""
    service = NotificationService(db)
    devices = await service.get_user_devices(current_user.id)
    return [DeviceResponse.model_validate(d) for d in devices]


@router.post("/devices", response_model=DeviceResponse)
async def register_device(
    device: DeviceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a device for push notifications."""
    service = NotificationService(db)
    new_device = await service.register_device(
        user_id=current_user.id,
        platform=device.platform,
        push_token=device.push_token,
        name=device.name,
        push_token_expires_at=device.push_token_expires_at,
    )
    return DeviceResponse.model_validate(new_device)


@router.delete("/devices/{device_id}")
async def unregister_device(
    device_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unregister a device."""
    service = NotificationService(db)
    unregistered = await service.unregister_device(device_id, current_user.id)
    if not unregistered:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"unregistered": True}
