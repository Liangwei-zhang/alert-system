from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from domains.account.repository import AccountRepository
from domains.auth.repository import UserRepository
from infra.core.errors import AppError
from infra.db.session import get_db_session

router = APIRouter(prefix="/v1/admin/users", tags=["admin", "users"])


class AdminUserResponse(BaseModel):
    id: int
    email: str
    name: str | None = None
    plan: str
    locale: str
    timezone: str
    subscription_status: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    total_capital: float | None = None
    currency: str | None = None
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AdminUserListResponse(BaseModel):
    data: list[AdminUserResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class UpdateAdminUserRequest(BaseModel):
    name: str | None = None
    plan: str | None = None
    locale: str | None = None
    timezone: str | None = None
    is_active: bool | None = None
    total_capital: float | None = None
    currency: str | None = None
    extra: dict[str, Any] | None = None


class BulkUpdateUsersRequest(BaseModel):
    user_ids: list[int] = Field(min_length=1)
    plan: str | None = None
    is_active: bool | None = None


class BulkUpdateUsersResponse(BaseModel):
    message: str
    updated_user_ids: list[int]
    users: list[AdminUserResponse]


def _to_response(user, account) -> AdminUserResponse:
    extra = dict(getattr(user, "extra", {}) or {})
    subscription = extra.get("subscription") if isinstance(extra.get("subscription"), dict) else {}
    return AdminUserResponse(
        id=int(user.id),
        email=str(user.email),
        name=str(user.name) if getattr(user, "name", None) else None,
        plan=str(user.plan),
        locale=str(user.locale),
        timezone=str(user.timezone),
        subscription_status=(
            str(subscription.get("status"))
            if isinstance(subscription, dict) and subscription.get("status")
            else None
        ),
        extra=extra,
        is_active=bool(user.is_active),
        total_capital=(
            float(account.total_capital)
            if account is not None and getattr(account, "total_capital", None) is not None
            else None
        ),
        currency=(
            str(account.currency)
            if account is not None and getattr(account, "currency", None)
            else None
        ),
        last_login_at=getattr(user, "last_login_at", None),
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("", response_model=AdminUserListResponse)
async def list_users(
    query: str | None = Query(None, description="Search by email or name"),
    plan: str | None = Query(None, description="Filter by plan"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=500, description="Results limit"),
    offset: int = Query(0, ge=0, description="Results offset"),
    db: AsyncSession = Depends(get_db_session),
) -> AdminUserListResponse:
    repository = UserRepository(db)
    rows = await repository.list_admin_users(
        limit=limit,
        offset=offset,
        query=query,
        plan=plan,
        is_active=is_active,
    )
    total = await repository.count_admin_users(query=query, plan=plan, is_active=is_active)
    return AdminUserListResponse(
        data=[_to_response(user, account) for user, account in rows],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(rows)) < total,
    )


@router.get("/{user_id}", response_model=AdminUserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> AdminUserResponse:
    user, account = await UserRepository(db).get_admin_user_detail(user_id)
    if user is None:
        raise AppError(
            code="admin_user_not_found",
            message="User not found",
            status_code=404,
        )
    return _to_response(user, account)


@router.put("/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: int,
    request: UpdateAdminUserRequest,
    db: AsyncSession = Depends(get_db_session),
) -> AdminUserResponse:
    user_repository = UserRepository(db)
    account_repository = AccountRepository(db)
    user = await user_repository.update_admin_user(
        user_id,
        name=request.name,
        plan=request.plan,
        locale=request.locale,
        timezone_name=request.timezone,
        is_active=request.is_active,
        extra=request.extra,
    )
    if user is None:
        raise AppError(
            code="admin_user_not_found",
            message="User not found",
            status_code=404,
        )
    if request.total_capital is not None or request.currency is not None:
        await account_repository.upsert_account(
            user_id,
            total_capital=request.total_capital,
            currency=request.currency,
        )
    user, account = await user_repository.get_admin_user_detail(user_id)
    return _to_response(user, account)


@router.post("/bulk", response_model=BulkUpdateUsersResponse)
async def bulk_update_users(
    request: BulkUpdateUsersRequest,
    db: AsyncSession = Depends(get_db_session),
) -> BulkUpdateUsersResponse:
    if request.plan is None and request.is_active is None:
        raise AppError(
            code="admin_bulk_update_empty",
            message="Bulk update requires at least one change",
            status_code=400,
        )
    repository = UserRepository(db)
    updated_user_ids = await repository.bulk_update_admin_users(
        request.user_ids,
        plan=request.plan,
        is_active=request.is_active,
    )
    rows = await repository.list_admin_users_by_ids(updated_user_ids)
    return BulkUpdateUsersResponse(
        message="Users updated",
        updated_user_ids=updated_user_ids,
        users=[_to_response(user, account) for user, account in rows],
    )
