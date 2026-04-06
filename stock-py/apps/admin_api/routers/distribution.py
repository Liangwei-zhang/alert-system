from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from domains.admin.distribution_service import ManualDistributionService
from domains.admin.repository import OperatorRepository
from infra.core.context import build_request_context
from infra.core.errors import AppError
from infra.db.session import get_db_session

router = APIRouter(prefix="/v1/admin/distribution", tags=["admin", "distribution"])

_ALLOWED_CHANNELS = {"email", "push"}


class ManualDistributionRequest(BaseModel):
    user_ids: list[int] = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)
    channels: list[str] = Field(min_length=1, max_length=10)
    notification_type: str = Field(default="manual.message", min_length=1, max_length=50)
    ack_required: bool = False
    ack_deadline_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class ManualDistributionResponse(BaseModel):
    message: str
    created_notifications: int
    requested_outbox: int
    resolved_user_ids: list[int]
    skipped_user_ids: list[int]
    notification_ids: list[str]
    outbox_ids: list[str]
    channels: list[str]


def _resolve_request_context(request: Request):
    return getattr(request.state, "request_context", None) or build_request_context(request)


async def _require_active_operator_id(request: Request, db: AsyncSession) -> tuple[int, Any]:
    context = _resolve_request_context(request)
    raw_operator_id = context.operator_id
    if raw_operator_id is None:
        raise AppError(
            code="admin_operator_required",
            message="X-Operator-ID header is required",
            status_code=400,
        )
    try:
        operator_user_id = int(str(raw_operator_id))
    except ValueError as exc:
        raise AppError(
            code="admin_operator_invalid",
            message="X-Operator-ID must be an integer",
            status_code=400,
        ) from exc
    operator, _user = await OperatorRepository(db).get_active_operator(
        operator_user_id,
        allowed_roles={"operator", "admin"},
    )
    if operator is None:
        raise AppError(
            code="admin_operator_forbidden",
            message="Active operator access is required",
            status_code=403,
        )
    return operator_user_id, context


@router.post("/manual-message", response_model=ManualDistributionResponse)
async def create_manual_message(
    request: ManualDistributionRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> ManualDistributionResponse:
    channels = sorted(
        {str(channel).strip().lower() for channel in request.channels if str(channel).strip()}
    )
    if not channels:
        raise AppError(
            code="admin_distribution_channels_empty",
            message="At least one delivery channel is required",
            status_code=400,
        )
    invalid_channels = [channel for channel in channels if channel not in _ALLOWED_CHANNELS]
    if invalid_channels:
        raise AppError(
            code="admin_distribution_channel_invalid",
            message=f"Unsupported channels: {', '.join(invalid_channels)}",
            status_code=400,
        )

    operator_user_id, context = await _require_active_operator_id(http_request, db)
    service = ManualDistributionService(db)
    result = await service.send_manual_message(
        operator_user_id=operator_user_id,
        context=context,
        user_ids=request.user_ids,
        title=request.title,
        body=request.body,
        channels=channels,
        notification_type=request.notification_type,
        ack_required=request.ack_required,
        ack_deadline_at=request.ack_deadline_at,
        metadata=request.metadata,
    )
    await OperatorRepository(db).touch_operator(operator_user_id)
    return ManualDistributionResponse(
        message="Manual distribution message queued",
        created_notifications=result.created_notifications,
        requested_outbox=result.requested_outbox,
        resolved_user_ids=result.resolved_user_ids,
        skipped_user_ids=result.skipped_user_ids,
        notification_ids=result.notification_ids,
        outbox_ids=result.outbox_ids,
        channels=channels,
    )
