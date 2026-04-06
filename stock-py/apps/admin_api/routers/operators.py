from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from domains.admin.repository import OperatorRepository
from infra.core.context import build_request_context
from infra.core.errors import AppError
from infra.db.session import get_db_session
from infra.events.outbox import OutboxPublisher

router = APIRouter(prefix="/v1/admin/operators", tags=["admin", "operators"])


class AdminOperatorResponse(BaseModel):
    user_id: int
    email: str
    name: str | None = None
    role: str
    scopes: list[str] = Field(default_factory=list)
    is_active: bool
    last_action_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AdminOperatorListResponse(BaseModel):
    data: list[AdminOperatorResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class UpdateAdminOperatorRequest(BaseModel):
    role: str | None = Field(None, pattern="^(viewer|operator|admin)$")
    scopes: list[str] | None = None
    is_active: bool | None = None


def _resolve_request_context(request: Request):
    return getattr(request.state, "request_context", None) or build_request_context(request)


def _to_response(operator, user) -> AdminOperatorResponse:
    return AdminOperatorResponse(
        user_id=int(operator.user_id),
        email=str(user.email),
        name=str(user.name) if getattr(user, "name", None) else None,
        role=str(getattr(operator.role, "value", operator.role)),
        scopes=list(getattr(operator, "scopes", []) or []),
        is_active=bool(operator.is_active),
        last_action_at=getattr(operator, "last_action_at", None),
        created_at=operator.created_at,
        updated_at=operator.updated_at,
    )


@router.get("", response_model=AdminOperatorListResponse)
async def list_operators(
    query: str | None = Query(None, description="Search by email or name"),
    role: str | None = Query(
        None, pattern="^(viewer|operator|admin)$", description="Filter by role"
    ),
    is_active: bool | None = Query(None, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=500, description="Results limit"),
    offset: int = Query(0, ge=0, description="Results offset"),
    db: AsyncSession = Depends(get_db_session),
) -> AdminOperatorListResponse:
    repository = OperatorRepository(db)
    rows = await repository.list_admin_operators(
        limit=limit,
        offset=offset,
        query=query,
        role=role,
        is_active=is_active,
    )
    total = await repository.count_admin_operators(query=query, role=role, is_active=is_active)
    return AdminOperatorListResponse(
        data=[_to_response(operator, user) for operator, user in rows],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(rows)) < total,
    )


@router.put("/{user_id}", response_model=AdminOperatorResponse)
async def upsert_operator(
    user_id: int,
    request: UpdateAdminOperatorRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> AdminOperatorResponse:
    if request.role is None and request.scopes is None and request.is_active is None:
        raise AppError(
            code="admin_operator_update_empty",
            message="Operator update requires at least one change",
            status_code=400,
        )
    repository = OperatorRepository(db)
    operator, user = await repository.upsert_operator(
        user_id,
        role=request.role,
        scopes=request.scopes,
        is_active=request.is_active,
    )
    if operator is None or user is None:
        raise AppError(
            code="admin_operator_user_not_found",
            message="User not found",
            status_code=404,
        )

    context = _resolve_request_context(http_request)
    await OutboxPublisher(db).publish_after_commit(
        topic="ops.audit.logged",
        key=f"operator:{user_id}",
        payload={
            "entity": "operator",
            "entity_id": str(user_id),
            "action": "role.updated",
            "source": "admin-api",
            "operator_id": context.operator_id,
            "role": str(getattr(operator.role, "value", operator.role)),
            "scopes": list(getattr(operator, "scopes", []) or []),
            "is_active": bool(operator.is_active),
            "request_id": context.request_id,
        },
        headers={
            "request_id": context.request_id,
            "operator_id": str(context.operator_id) if context.operator_id is not None else "",
        },
    )
    return _to_response(operator, user)
