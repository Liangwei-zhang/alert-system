from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from domains.signals.desktop_signal_service import DesktopSignalService
from domains.signals.schemas import DesktopSignalIngestResponse, DesktopSignalRequest
from infra.core.config import get_settings
from infra.core.errors import AppError
from infra.db.session import get_db_session

router = APIRouter(prefix="/internal/signals", tags=["signal-ingest"])


async def require_internal_signal_secret(
    x_internal_signal_secret: str | None = Header(default=None),
) -> None:
    settings = get_settings()
    if not settings.internal_signal_ingest_secret:
        if settings.debug:
            return
        raise AppError(
            "internal_signal_secret_missing",
            "Internal signal ingest secret is not configured",
            status_code=503,
        )
    if x_internal_signal_secret != settings.internal_signal_ingest_secret:
        raise AppError(
            "internal_signal_forbidden",
            "Invalid internal signal ingest secret",
            status_code=403,
        )


@router.post("/desktop", response_model=DesktopSignalIngestResponse)
async def ingest_desktop_signal(
    request: DesktopSignalRequest,
    _authorized: None = Depends(require_internal_signal_secret),
    session: AsyncSession = Depends(get_db_session),
) -> DesktopSignalIngestResponse:
    result = await DesktopSignalService(session).ingest_desktop_signal(request)
    return DesktopSignalIngestResponse(**result)
