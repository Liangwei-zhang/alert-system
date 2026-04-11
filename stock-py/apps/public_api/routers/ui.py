from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from apps.public_api.ui_shell import SurfaceName, render_surface_page
from infra.core.config import get_settings

router = APIRouter(tags=["ui"])

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ADMIN_FRONTEND_DIR = _REPO_ROOT / "frontend" / "admin"
_APP_FRONTEND_DIR = _REPO_ROOT / "frontend" / "app"
_PLATFORM_FRONTEND_DIR = _REPO_ROOT / "frontend" / "platform"
_NEXT_ROUTE_PREFIX = "/next"
_UI_VERSIONS_PATH = "/ui-versions/"
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


def _render_page(
    *,
    surface: SurfaceName,
    public_api_base_url: str | None,
    admin_api_base_url: str | None,
    route_prefix: str | None = None,
    switcher_path: str | None = None,
    experimental: bool = False,
) -> HTMLResponse:
    settings = get_settings()
    return HTMLResponse(
        render_surface_page(
            surface=surface,
            project_name=settings.project_name,
            public_api_base_url=public_api_base_url,
            admin_api_base_url=admin_api_base_url,
            route_prefix=route_prefix,
            switcher_path=switcher_path,
            experimental=experimental,
        ),
        headers={"Cache-Control": "no-store"},
    )


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


def _render_version_switcher(
    *,
    public_api_base_url: str | None,
    admin_api_base_url: str | None,
) -> HTMLResponse:
    settings = get_settings()
    suffix = _build_query_suffix(
        public_api_base_url=public_api_base_url,
        admin_api_base_url=admin_api_base_url,
    )

    def card(*, title: str, tone: str, description: str, stable_href: str, next_href: str) -> str:
        return f"""
        <article class=\"card\">
            <div class=\"card-head\">
                <div>
                    <div class=\"tag {tone}\">{tone}</div>
                    <h2>{title}</h2>
                </div>
            </div>
            <p>{description}</p>
            <div class=\"actions\">
                <a class=\"btn primary\" href=\"{next_href}{suffix}\">打开新版</a>
                <a class=\"btn\" href=\"{stable_href}{suffix}\">打开稳定版</a>
            </div>
        </article>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang=\"zh-CN\">
    <head>
        <meta charset=\"UTF-8\">
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
        <title>{settings.project_name} 前端版本切换</title>
        <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">
        <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>
        <link href=\"https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Space+Grotesk:wght@400;500;600;700&display=swap\" rel=\"stylesheet\">
        <style>
            :root {{
                color-scheme: light;
                --bg: #f6f1e8;
                --panel: rgba(255,255,255,0.82);
                --ink: #1b2624;
                --muted: #64736f;
                --line: rgba(27,38,36,0.12);
                --accent: #0d7c6b;
                --accent-strong: #0b5f52;
                --shadow: 0 22px 50px rgba(27,38,36,0.10);
                --radius: 28px;
            }}
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                min-height: 100vh;
                font-family: \"Space Grotesk\", \"Segoe UI\", sans-serif;
                color: var(--ink);
                background:
                    radial-gradient(circle at top left, rgba(13,124,107,0.16), transparent 28%),
                    radial-gradient(circle at bottom right, rgba(214,167,94,0.18), transparent 26%),
                    linear-gradient(180deg, #fcfaf6 0%, var(--bg) 100%);
            }}
            .shell {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 56px; }}
            .hero {{
                padding: 28px;
                border-radius: 32px;
                background: var(--panel);
                border: 1px solid var(--line);
                box-shadow: var(--shadow);
                backdrop-filter: blur(18px);
            }}
            .hero h1 {{ margin: 0 0 12px; font-family: \"Fraunces\", Georgia, serif; font-size: clamp(2rem, 5vw, 3.6rem); line-height: 0.98; letter-spacing: -0.05em; }}
            .hero p {{ margin: 0; max-width: 70ch; color: var(--muted); line-height: 1.7; }}
            .note {{ margin-top: 14px; display: inline-flex; padding: 8px 12px; border-radius: 999px; background: rgba(13,124,107,0.1); color: var(--accent-strong); font-size: 0.92rem; }}
            .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; margin-top: 22px; }}
            .card {{ padding: 22px; border-radius: var(--radius); background: var(--panel); border: 1px solid var(--line); box-shadow: var(--shadow); backdrop-filter: blur(18px); }}
            .card-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; }}
            .card h2 {{ margin: 10px 0 8px; font-family: \"Fraunces\", Georgia, serif; font-size: 1.5rem; letter-spacing: -0.04em; }}
            .card p {{ margin: 0; color: var(--muted); line-height: 1.7; min-height: 88px; }}
            .tag {{ display: inline-flex; padding: 6px 10px; border-radius: 999px; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.08em; }}
            .tag.stable {{ background: rgba(27,38,36,0.08); color: var(--ink); }}
            .tag.parallel {{ background: rgba(13,124,107,0.12); color: var(--accent-strong); }}
            .actions {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }}
            .btn {{ text-decoration: none; color: var(--ink); padding: 11px 16px; border-radius: 999px; border: 1px solid var(--line); background: rgba(255,255,255,0.72); font-weight: 600; }}
            .btn.primary {{ background: var(--accent); border-color: transparent; color: #fff; }}
            .meta {{ margin-top: 18px; color: var(--muted); font-size: 0.92rem; }}
            @media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} }}
        </style>
    </head>
    <body>
        <main class=\"shell\">
            <section class=\"hero\">
                <h1>并行新前端已就绪</h1>
                <p>现有页面保持不变，稳定版继续走原来的静态前端；新版通过独立路由提供，不满意时可立即切回，不会覆盖你现在在用的页面。</p>
                <div class=\"note\">稳定版保留在 /app /platform /admin，新版保留在 /next/app /next/platform /next/admin</div>
                <div class=\"meta\">项目：{settings.project_name} · 目的：并行试用、随时回退、零覆盖现有前端文件</div>
            </section>
            <section class=\"grid\">
                {card(title='订阅端', tone='parallel', description='新版订阅端使用 Python 直接渲染的并行 UI Shell，适合在不改现有移动页的前提下试新版信息结构。', stable_href='/app/', next_href='/next/app/')}
                {card(title='平台端', tone='parallel', description='新版平台端保留原有数据接口，但把候选标的、策略参数、交易执行和高权限策略观测收口到同一套策略核心工作台中，和旧驾驶舱完全并行。', stable_href='/platform/', next_href='/next/platform/')}
                {card(title='管理端', tone='parallel', description='新版管理端单独挂在并行路由下，便于试新结构、表单和控制台组织方式，不影响现有 admin 页面。', stable_href='/admin/', next_href='/next/admin/')}
            </section>
        </main>
    </body>
    </html>
    """
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


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


@router.get("/ui-versions", include_in_schema=False)
async def ui_versions_redirect(
    public_api_base_url: str | None = Query(default=None),
    admin_api_base_url: str | None = Query(default=None),
) -> RedirectResponse:
    suffix = _build_query_suffix(
        public_api_base_url=public_api_base_url,
        admin_api_base_url=admin_api_base_url,
    )
    return RedirectResponse(url=f"{_UI_VERSIONS_PATH}{suffix}", status_code=307)


@router.get("/ui-versions/", include_in_schema=False)
async def ui_versions_index(
    public_api_base_url: str | None = Query(default=None),
    admin_api_base_url: str | None = Query(default=None),
) -> HTMLResponse:
    return _render_version_switcher(
        public_api_base_url=public_api_base_url,
        admin_api_base_url=admin_api_base_url,
    )


@router.get("/next", include_in_schema=False)
async def next_root_redirect(
    public_api_base_url: str | None = Query(default=None),
    admin_api_base_url: str | None = Query(default=None),
) -> RedirectResponse:
    suffix = _build_query_suffix(
        public_api_base_url=public_api_base_url,
        admin_api_base_url=admin_api_base_url,
    )
    return RedirectResponse(url=f"{_UI_VERSIONS_PATH}{suffix}", status_code=307)


@router.get("/next/app", include_in_schema=False)
async def next_app_redirect(
    public_api_base_url: str | None = Query(default=None),
    admin_api_base_url: str | None = Query(default=None),
) -> RedirectResponse:
    suffix = _build_query_suffix(
        public_api_base_url=public_api_base_url,
        admin_api_base_url=admin_api_base_url,
    )
    return RedirectResponse(url=f"{_NEXT_ROUTE_PREFIX}/app/{suffix}", status_code=307)


@router.get("/next/app/", include_in_schema=False)
async def next_app_page(
    public_api_base_url: str | None = Query(default=None),
    admin_api_base_url: str | None = Query(default=None),
) -> HTMLResponse:
    return _render_page(
        surface="app",
        public_api_base_url=public_api_base_url,
        admin_api_base_url=admin_api_base_url,
        route_prefix=_NEXT_ROUTE_PREFIX,
        switcher_path=_UI_VERSIONS_PATH,
        experimental=True,
    )


@router.get("/next/platform", include_in_schema=False)
async def next_platform_redirect(
    public_api_base_url: str | None = Query(default=None),
    admin_api_base_url: str | None = Query(default=None),
) -> RedirectResponse:
    suffix = _build_query_suffix(
        public_api_base_url=public_api_base_url,
        admin_api_base_url=admin_api_base_url,
    )
    return RedirectResponse(url=f"{_NEXT_ROUTE_PREFIX}/platform/{suffix}", status_code=307)


@router.get("/next/platform/", include_in_schema=False)
async def next_platform_page(
    public_api_base_url: str | None = Query(default=None),
    admin_api_base_url: str | None = Query(default=None),
) -> HTMLResponse:
    return _render_page(
        surface="platform",
        public_api_base_url=public_api_base_url,
        admin_api_base_url=admin_api_base_url,
        route_prefix=_NEXT_ROUTE_PREFIX,
        switcher_path=_UI_VERSIONS_PATH,
        experimental=True,
    )


@router.get("/next/admin", include_in_schema=False)
async def next_admin_redirect(
    public_api_base_url: str | None = Query(default=None),
    admin_api_base_url: str | None = Query(default=None),
) -> RedirectResponse:
    suffix = _build_query_suffix(
        public_api_base_url=public_api_base_url,
        admin_api_base_url=admin_api_base_url,
    )
    return RedirectResponse(url=f"{_NEXT_ROUTE_PREFIX}/admin/{suffix}", status_code=307)


@router.get("/next/admin/", include_in_schema=False)
async def next_admin_page(
    public_api_base_url: str | None = Query(default=None),
    admin_api_base_url: str | None = Query(default=None),
) -> HTMLResponse:
    return _render_page(
        surface="admin",
        public_api_base_url=public_api_base_url,
        admin_api_base_url=admin_api_base_url,
        route_prefix=_NEXT_ROUTE_PREFIX,
        switcher_path=_UI_VERSIONS_PATH,
        experimental=True,
    )


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