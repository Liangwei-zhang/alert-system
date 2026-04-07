from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from domains.auth.schemas import (
    AdminAuthSessionResponse,
    LogoutRequest,
    LogoutResponse,
    RefreshTokenRequest,
    SendCodeRequest,
    SendCodeResponse,
    VerifyCodeRequest,
)
from domains.auth.service import AuthService
from infra.db.session import get_db_session

router = APIRouter(prefix="/admin-auth", tags=["admin-auth"])


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post("/send-code", response_model=SendCodeResponse)
async def send_code(
    data: SendCodeRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> SendCodeResponse:
    service = AuthService(session)
    return await service.send_admin_code(data.email, ip=_client_ip(request))


@router.post("/verify", response_model=AdminAuthSessionResponse)
async def verify_code(
    data: VerifyCodeRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> AdminAuthSessionResponse:
    service = AuthService(session)
    return await service.verify_admin_code(
        email=data.email,
        code=data.code,
        locale=data.locale,
        timezone_name=data.timezone,
        device_info={
            "ip": _client_ip(request),
            "user_agent": request.headers.get("User-Agent", ""),
        },
    )


@router.post("/refresh", response_model=AdminAuthSessionResponse)
async def refresh(
    data: RefreshTokenRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AdminAuthSessionResponse:
    service = AuthService(session)
    return await service.refresh_admin(data.refresh_token)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    data: LogoutRequest | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> LogoutResponse:
    authorization = request.headers.get("Authorization", "")
    access_token = authorization[7:] if authorization.startswith("Bearer ") else ""
    service = AuthService(session)
    await service.logout_tokens(
        access_token=access_token or None,
        refresh_token=data.refresh_token if data else None,
    )
    return LogoutResponse(message="Signed out successfully")