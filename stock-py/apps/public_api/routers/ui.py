from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, RedirectResponse, Response

router = APIRouter(tags=["ui"])

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ADMIN_FRONTEND_DIR = _REPO_ROOT / "frontend" / "admin"
_APP_FRONTEND_DIR = _REPO_ROOT / "frontend" / "app"
_PLATFORM_FRONTEND_DIR = _REPO_ROOT / "frontend" / "platform"
_PLATFORM_ROUTE_PRESETS = {
    "workspace": {"mode": "overview", "section": "trading-agents-panel"},
    "signals": {"mode": "signals", "section": "watchlist-panel"},
    "decisions": {"mode": "signals", "section": "decision-tape-panel"},
    "execution": {"mode": "execution", "section": "exit-desk-panel"},
    "backtests": {"mode": "research", "section": "backtest-panel"},
    "health": {"mode": "research", "section": "health-panel"},
    "tradingagents": {"mode": "research", "section": "trading-agents-panel"},
}
_ADMIN_PAGE_ALIASES = {
    "dashboard": "index.html",
    "people": "people.html",
    "communications": "communications.html",
    "intelligence": "intelligence.html",
    "experiments": "experiments.html",
    "runtime": "runtime.html",
    "api": "api.html",
}


def _resolve_app_asset(asset_path: str) -> Path:
    requested = (asset_path or "index.html").lstrip("/")
    candidate = (_APP_FRONTEND_DIR / requested).resolve()
    try:
        candidate.relative_to(_APP_FRONTEND_DIR)
    except ValueError:
        raise FileNotFoundError(requested)
    if not candidate.is_file():
        raise FileNotFoundError(requested)
    return candidate


def _resolve_platform_asset(asset_path: str) -> Path:
    requested = (asset_path or "index.html").lstrip("/")
    candidate = (_PLATFORM_FRONTEND_DIR / requested).resolve()
    try:
        candidate.relative_to(_PLATFORM_FRONTEND_DIR)
    except ValueError:
        raise FileNotFoundError(requested)
    if not candidate.is_file():
        raise FileNotFoundError(requested)
    return candidate


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


def _build_query_suffix(
    *,
    public_api_base_url: str | None,
    admin_api_base_url: str | None,
    extra_params: dict[str, str | None] | None = None,
) -> str:
    query: list[tuple[str, str]] = []
    if public_api_base_url:
        query.append(("public_api_base_url", public_api_base_url))
    if admin_api_base_url:
        query.append(("admin_api_base_url", admin_api_base_url))
    if extra_params:
        for key, value in extra_params.items():
            text = str(value or "").strip()
            if text:
                query.append((key, text))
    return f"?{urlencode(query, doseq=True)}" if query else ""


def _static_file_response(file_path: Path) -> FileResponse:
    return FileResponse(
        file_path,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


def _platform_alias_redirect(
    *,
    view_name: str,
    public_api_base_url: str | None,
    admin_api_base_url: str | None,
    symbol: str | None,
) -> RedirectResponse:
    preset = _PLATFORM_ROUTE_PRESETS[view_name]
    suffix = _build_query_suffix(
        public_api_base_url=public_api_base_url,
        admin_api_base_url=admin_api_base_url,
        extra_params={
            "mode": preset["mode"],
            "section": preset["section"],
            "symbol": symbol,
        },
    )
    return RedirectResponse(url=f"/platform/{suffix}", status_code=307)


@router.get("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    return FileResponse(
        _ADMIN_FRONTEND_DIR / "favicon.ico",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/app", include_in_schema=False)
async def subscriber_page_redirect(
    public_api_base_url: str | None = Query(default=None),
    admin_api_base_url: str | None = Query(default=None),
) -> RedirectResponse:
    suffix = _build_query_suffix(
        public_api_base_url=public_api_base_url,
        admin_api_base_url=admin_api_base_url,
    )
    return RedirectResponse(url=f"/app/{suffix}", status_code=307)


@router.get("/app/", include_in_schema=False)
async def app_page_index() -> FileResponse:
    return _static_file_response(_resolve_app_asset("index.html"))


@router.get("/app/{asset_path:path}", include_in_schema=False)
async def app_page_assets(asset_path: str) -> FileResponse:
    try:
        return _static_file_response(_resolve_app_asset(asset_path))
    except FileNotFoundError:
        # Fallback to index if navigating via single page app routing
        return _static_file_response(_resolve_app_asset("index.html"))

@router.get("/platform", include_in_schema=False)
async def platform_page_redirect(
    public_api_base_url: str | None = Query(default=None),
    admin_api_base_url: str | None = Query(default=None),
) -> RedirectResponse:
    suffix = _build_query_suffix(
        public_api_base_url=public_api_base_url,
        admin_api_base_url=admin_api_base_url,
    )
    return RedirectResponse(url=f"/platform/{suffix}", status_code=307)

@router.get("/platform/", include_in_schema=False)
async def platform_page_index() -> FileResponse:
    return _static_file_response(_resolve_platform_asset("index.html"))


@router.get("/platform/{page_name}", include_in_schema=False)
@router.get("/platform/{page_name}/", include_in_schema=False)
async def platform_page_entry(
    page_name: str,
    public_api_base_url: str | None = Query(default=None),
    admin_api_base_url: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
) -> Response:
    normalized_page = page_name.rstrip("/")
    if normalized_page in _PLATFORM_ROUTE_PRESETS:
        return _platform_alias_redirect(
            view_name=normalized_page,
            public_api_base_url=public_api_base_url,
            admin_api_base_url=admin_api_base_url,
            symbol=symbol,
        )
    try:
        return _static_file_response(_resolve_platform_asset(normalized_page))
    except FileNotFoundError:
        return _static_file_response(_resolve_platform_asset("index.html"))

@router.get("/platform/{asset_path:path}", include_in_schema=False)
async def platform_page_assets(asset_path: str) -> FileResponse:
    file_path = _resolve_platform_asset(asset_path)
    return _static_file_response(file_path)



@router.get("/admin", include_in_schema=False)
async def admin_page_redirect(
    public_api_base_url: str | None = Query(default=None),
    admin_api_base_url: str | None = Query(default=None),
) -> RedirectResponse:
    suffix = _build_query_suffix(
        public_api_base_url=public_api_base_url,
        admin_api_base_url=admin_api_base_url,
    )
    return RedirectResponse(url=f"/admin/{suffix}", status_code=307)


@router.get("/admin/", include_in_schema=False)
async def admin_page_index() -> FileResponse:
    return _static_file_response(_resolve_admin_asset("index.html"))


@router.get("/admin/{page_name}", include_in_schema=False)
@router.get("/admin/{page_name}/", include_in_schema=False)
async def admin_page_entry(page_name: str) -> FileResponse:
    normalized_page = page_name.rstrip("/")
    asset_name = _ADMIN_PAGE_ALIASES.get(normalized_page, normalized_page)
    return _static_file_response(_resolve_admin_asset(asset_name))


@router.get("/admin/{asset_path:path}", include_in_schema=False)
async def admin_page_assets(asset_path: str) -> FileResponse:
    file_path = _resolve_admin_asset(asset_path)
    return _static_file_response(file_path)