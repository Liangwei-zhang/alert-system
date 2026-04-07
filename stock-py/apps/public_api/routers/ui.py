from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from apps.public_api.ui_shell import SurfaceName, render_surface_page
from infra.core.config import get_settings

router = APIRouter(tags=["ui"])

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ADMIN_FRONTEND_DIR = _REPO_ROOT / "frontend" / "admin"


def _resolve_admin_asset(asset_path: str) -> Path:
    requested = (asset_path or "index.html").lstrip("/")
    candidate = (_ADMIN_FRONTEND_DIR / requested).resolve()
    try:
        candidate.relative_to(_ADMIN_FRONTEND_DIR)
    except ValueError:
        raise FileNotFoundError(requested)
    if not candidate.is_file():
        raise FileNotFoundError(requested)
    return candidate


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


@router.get("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    return FileResponse(
        _ADMIN_FRONTEND_DIR / "favicon.ico",
        headers={"Cache-Control": "public, max-age=86400"},
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


@router.get("/admin", include_in_schema=False)
async def admin_page_redirect(
    public_api_base_url: str | None = Query(default=None),
    admin_api_base_url: str | None = Query(default=None),
) -> RedirectResponse:
    query = []
    if public_api_base_url:
        query.append(f"public_api_base_url={public_api_base_url}")
    if admin_api_base_url:
        query.append(f"admin_api_base_url={admin_api_base_url}")
    suffix = f"?{'&'.join(query)}" if query else ""
    return RedirectResponse(url=f"/admin/{suffix}", status_code=307)


@router.get("/admin/", include_in_schema=False)
async def admin_page_index() -> FileResponse:
    index_path = _resolve_admin_asset("index.html")
    return FileResponse(
        index_path,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get("/admin/{asset_path:path}", include_in_schema=False)
async def admin_page_assets(asset_path: str) -> FileResponse:
    file_path = _resolve_admin_asset(asset_path)
    headers = {"Cache-Control": "no-store, no-cache, must-revalidate"}
    return FileResponse(file_path, headers=headers)