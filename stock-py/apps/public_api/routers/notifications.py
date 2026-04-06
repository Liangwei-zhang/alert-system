from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from domains.notifications.command_service import NotificationCommandService
from domains.notifications.push_service import PushSubscriptionService
from domains.notifications.query_service import NotificationQueryService
from domains.notifications.repository import (
    DeliveryAttemptRepository,
    NotificationRepository,
    PushSubscriptionRepository,
    ReceiptRepository,
)
from domains.notifications.schemas import (
    NotificationAcknowledgeResponse,
    NotificationCommandResponse,
    NotificationListQuery,
    NotificationListResponse,
    PushDeviceResponse,
    RegisterPushDeviceRequest,
    TestPushResponse,
)
from infra.db.session import get_db_session
from infra.security.auth import CurrentUser, require_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _query_service(session: AsyncSession) -> NotificationQueryService:
    return NotificationQueryService(
        notification_repository=NotificationRepository(session),
        push_subscription_repository=PushSubscriptionRepository(session),
        receipt_repository=ReceiptRepository(session),
    )


def _command_service(session: AsyncSession) -> NotificationCommandService:
    return NotificationCommandService(
        notification_repository=NotificationRepository(session),
        receipt_repository=ReceiptRepository(session),
    )


def _push_service(session: AsyncSession) -> PushSubscriptionService:
    return PushSubscriptionService(
        push_subscription_repository=PushSubscriptionRepository(session),
        delivery_attempt_repository=DeliveryAttemptRepository(session),
    )


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    query: NotificationListQuery = Depends(),
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> NotificationListResponse:
    return await _query_service(session).list_notifications(
        user_id=current_user.user_id,
        cursor=query.cursor,
        limit=query.limit,
    )


@router.get("/push-devices", response_model=list[PushDeviceResponse])
async def list_push_devices(
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[PushDeviceResponse]:
    return await _query_service(session).list_push_devices(current_user.user_id)


@router.post(
    "/push-devices", response_model=PushDeviceResponse, status_code=status.HTTP_201_CREATED
)
async def register_push_device(
    data: RegisterPushDeviceRequest,
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> PushDeviceResponse:
    return await _push_service(session).register_device(current_user.user_id, data)


@router.delete("/push-devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disable_push_device(
    device_id: str,
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    await _push_service(session).disable_device(current_user.user_id, device_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/push-devices/{device_id}/test", response_model=TestPushResponse)
async def test_push_device(
    device_id: str,
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> TestPushResponse:
    return await _push_service(session).send_test_push(current_user.user_id, device_id)


@router.put("/read-all", response_model=NotificationCommandResponse)
async def mark_all_read(
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> NotificationCommandResponse:
    await _command_service(session).mark_all_read(current_user.user_id)
    return NotificationCommandResponse(message="All notifications marked as read")


@router.put("/{notification_id}/read", response_model=NotificationCommandResponse)
async def mark_read(
    notification_id: str,
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> NotificationCommandResponse:
    await _command_service(session).mark_read(current_user.user_id, notification_id)
    return NotificationCommandResponse(message="Notification marked as read")


@router.put("/{notification_id}/ack", response_model=NotificationAcknowledgeResponse)
async def acknowledge(
    notification_id: str,
    current_user: CurrentUser = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> NotificationAcknowledgeResponse:
    receipt = await _command_service(session).acknowledge(current_user.user_id, notification_id)
    return NotificationAcknowledgeResponse(
        message="Notification acknowledged",
        acknowledged=receipt is not None,
        acknowledged_at=getattr(receipt, "acknowledged_at", None),
    )
