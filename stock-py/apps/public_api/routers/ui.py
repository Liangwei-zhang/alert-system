from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from apps.public_api.ui_shell import SurfaceName, render_surface_page
from infra.core.config import get_settings

router = APIRouter(tags=["ui"])


def _render_page(
    *,
    surface: SurfaceName,
    public_api_base_url: str | None,
    admin_api_base_url: str | None,
) -> HTMLResponse:
    settings = get_settings()
    return HTMLResponse(
        render_surface_page(
            surface=surface,
            project_name=settings.project_name,
            public_api_base_url=public_api_base_url,
            admin_api_base_url=admin_api_base_url,
        ),
        headers={"Cache-Control": "no-store"},
    )


@router.get("/app", response_class=HTMLResponse, include_in_schema=False)
async def subscriber_page(
    public_api_base_url: str | None = Query(default=None),
    admin_api_base_url: str | None = Query(default=None),
) -> HTMLResponse:
    return _render_page(
        surface="app",
        public_api_base_url=public_api_base_url,
        admin_api_base_url=admin_api_base_url,
    )


@router.get("/platform", response_class=HTMLResponse, include_in_schema=False)
async def platform_page(
    public_api_base_url: str | None = Query(default=None),
    admin_api_base_url: str | None = Query(default=None),
) -> HTMLResponse:
    return _render_page(
        surface="platform",
        public_api_base_url=public_api_base_url,
        admin_api_base_url=admin_api_base_url,
    )


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_page(
    public_api_base_url: str | None = Query(default=None),
    admin_api_base_url: str | None = Query(default=None),
) -> HTMLResponse:
    return _render_page(
        surface="admin",
        public_api_base_url=public_api_base_url,
        admin_api_base_url=admin_api_base_url,
    )