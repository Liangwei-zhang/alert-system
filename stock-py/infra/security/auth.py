from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.core.errors import AppError
from infra.db.models.auth import SessionModel
from infra.db.session import get_db_session
from infra.security.session_cache import cache_active_session, get_cached_session_user_id
from infra.security.token_signer import get_token_signer

bearer_scheme = HTTPBearer(auto_error=False)
HEALTH_EXEMPT_PATHS = frozenset({"/health", "/health/ready", "/health/live"})


class CurrentUser(BaseModel):
    user_id: int
    plan: str = "free"
    scopes: list[str] = Field(default_factory=list)
    is_admin: bool = False


def _build_current_user(payload: dict[str, Any]) -> CurrentUser:
    subject = payload.get("sub")
    if subject is None:
        raise AppError("invalid_token", "Token subject is missing", status_code=401)

    scopes = payload.get("scopes") or []
    if not isinstance(scopes, list):
        scopes = [str(scopes)]

    return CurrentUser(
        user_id=int(subject),
        plan=str(payload.get("plan", "free")),
        scopes=[str(scope) for scope in scopes],
        is_admin=bool(payload.get("is_admin", False)),
    )


async def require_user(
    request: Request = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> CurrentUser:
    if request is not None and request.url.path in HEALTH_EXEMPT_PATHS:
        return CurrentUser(user_id=0, plan="system", scopes=["health"], is_admin=True)

    if credentials is None:
        raise AppError("auth_required", "Authentication is required", status_code=401)

    try:
        payload = get_token_signer().verify(credentials.credentials)
    except JWTError as exc:
        raise AppError("invalid_token", "Token validation failed", status_code=401) from exc

    if payload.get("type", "access") != "access":
        raise AppError("invalid_token", "Access token is required", status_code=401)

    user = _build_current_user(payload)
    token_hash = hashlib.sha256(credentials.credentials.encode("utf-8")).hexdigest()
    cached_user_id = await get_cached_session_user_id(token_hash)
    if cached_user_id is not None:
        if cached_user_id != user.user_id:
            raise AppError("invalid_token", "Token subject mismatch", status_code=401)
        return user

    result = await session.execute(
        select(SessionModel).where(
            SessionModel.token_hash == token_hash,
            SessionModel.expires_at > datetime.now(timezone.utc),
        )
    )
    session_record = result.scalar_one_or_none()
    if session_record is None:
        raise AppError("session_revoked", "Session is no longer active", status_code=401)

    if session_record.user_id != user.user_id:
        raise AppError("invalid_token", "Token subject mismatch", status_code=401)

    await cache_active_session(token_hash, session_record.user_id, session_record.expires_at)

    return user


async def require_admin(user: CurrentUser = Depends(require_user)) -> CurrentUser:
    if not user.is_admin:
        raise AppError("forbidden", "Admin access is required", status_code=403)
    return user
