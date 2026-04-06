"""
WebPush API endpoints - Device subscription management.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from infra.database import get_db
from domains.notifications.notification import (
    Device, DeviceCreate, DeviceResponse, 
    WebPushSubscriptionCreate, WebPushSubscriptionResponse
)
from apps.workers.push_dispatch.webpush_service import (
    get_vapid_public_key, WebPushService, WebPushPayload
)

router = APIRouter(prefix="/webpush", tags=["webpush"])


@router.get("/public-key", response_model=dict)
async def get_public_key():
    """
    Get the VAPID public key for client subscription.
    Clients need this key to subscribe to push notifications.
    """
    public_key = get_vapid_public_key()
    if not public_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WebPush not configured"
        )
    return {"public_key": public_key}


@router.post("/subscribe", response_model=DeviceResponse)
async def subscribe(
    subscription: WebPushSubscriptionCreate,
    db: Session = Depends(get_db),
    user_id: int = 1  # TODO: Get from auth
):
    """
    Register a WebPush subscription for the current user.
    
    The client should call this with the subscription object obtained
    from the browser's PushManager.subscribe() method.
    """
    # Check if subscription already exists
    existing = db.query(Device).filter(
        Device.subscription_endpoint == subscription.endpoint,
        Device.platform == "webpush"
    ).first()
    
    if existing:
        # Update existing subscription
        existing.vapid_public_key = subscription.p256dh
        existing.vapid_auth_key = subscription.auth
        existing.is_active = True
        existing.last_used_at = func.now()
        db.commit()
        db.refresh(existing)
        return existing
    
    # Create new device/subscription
    device = Device(
        user_id=user_id,
        platform="webpush",
        subscription_endpoint=subscription.endpoint,
        vapid_public_key=subscription.p256dh,
        vapid_auth_key=subscription.auth,
        is_active=True
    )
    
    db.add(device)
    db.commit()
    db.refresh(device)
    
    return device


@router.delete("/unsubscribe/{device_id}", response_model=dict)
async def unsubscribe(
    device_id: int,
    db: Session = Depends(get_db),
    user_id: int = 1  # TODO: Get from auth
):
    """
    Unsubscribe/remove a WebPush subscription.
    """
    device = db.query(Device).filter(
        Device.id == device_id,
        Device.user_id == user_id,
        Device.platform == "webpush"
    ).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    device.is_active = False
    db.commit()
    
    return {"status": "unsubscribed"}


@router.get("/subscriptions", response_model=list[DeviceResponse])
async def list_subscriptions(
    db: Session = Depends(get_db),
    user_id: int = 1  # TODO: Get from auth
):
    """
    List all active WebPush subscriptions for the current user.
    """
    subscriptions = db.query(Device).filter(
        Device.user_id == user_id,
        Device.platform == "webpush",
        Device.is_active == True
    ).all()
    
    return subscriptions


@router.post("/test", response_model=dict)
async def send_test_notification(
    db: Session = Depends(get_db),
    user_id: int = 1  # TODO: Get from auth
):
    """
    Send a test notification to verify WebPush is working.
    """
    service = WebPushService(db)
    
    payload = WebPushPayload(
        title="Test Notification",
        body="WebPush is working! 🎉",
        url="/",
        tag="test"
    )
    
    result = await service.send_notification(user_id, payload)
    
    return result


# Import func for SQLAlchemy
from sqlalchemy import func