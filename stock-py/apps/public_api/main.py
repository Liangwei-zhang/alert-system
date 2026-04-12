from __future__ import annotations

from contextlib import asynccontextmanager
from time import perf_counter
from typing import Literal

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from apps.public_api.routers import (
    account,
    admin_auth,
    auth,
    chart_data,
    monitoring,
    notifications,
    portfolio,
    search,
    sidecars,
    strategy_breakdown,
    signal_ingest,
    trades,
    tradingagents_submit,
    tradingagents_webhook,
    ui,
    watchlist,
)
from infra.cache.redis_client import close_redis
from infra.core.config import get_settings
from infra.core.context import build_request_context, reset_request_context, set_request_context
from infra.core.errors import register_exception_handlers
from infra.core.logging import configure_logging
from infra.db.session import dispose_engine
from infra.http.health import router as health_router
from infra.http.http_client import get_http_client_factory
from infra.observability.metrics import get_http_request_tracker, get_metrics_registry
from infra.observability.tracing import configure_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_tracing("public-api")
    app.state.webhook_secret = settings.tradingagents_webhook_secret
    app.state.tradingagents_webhook_auth_token = settings.tradingagents_webhook_auth_token
    yield
    await close_redis()
    await get_http_client_factory().aclose()
    await dispose_engine()


settings = get_settings()
metrics = get_metrics_registry()
http_request_tracker = get_http_request_tracker("public-api")

cors_allowed_origins = list(settings.allowed_origins)
cors_allow_origin_regex = None
if "*" in cors_allowed_origins:
    # Wildcard + credentials can behave inconsistently across clients.
    cors_allowed_origins = []
    cors_allow_origin_regex = r"https?://.*"

app = FastAPI(
    title=f"{settings.project_name} Public API",
    version=settings.version,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins,
    allow_origin_regex=cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def attach_request_context(request: Request, call_next):
    context = build_request_context(request)
    token = set_request_context(context)
    request.state.request_context = context
    start_time = perf_counter()
    response = None
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration_ms = (perf_counter() - start_time) * 1000
        metrics.counter("http_requests_total", "Total public API requests").inc()
        if status_code >= 500:
            metrics.counter(
                "http_request_errors_total",
                "Total public API 5xx responses",
            ).inc()
        metrics.histogram(
            "http_request_duration_ms",
            "Public API request latency in milliseconds",
        ).observe(duration_ms)
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        http_request_tracker.record(
            method=request.method,
            path=route_path,
            status_code=status_code,
            duration_ms=duration_ms,
        )
        reset_request_context(token)
        if response is not None:
            response.headers["X-Request-ID"] = context.request_id


app.include_router(health_router)
app.include_router(ui.router)
app.include_router(monitoring.router)
app.include_router(auth.router, prefix="/v1")
app.include_router(admin_auth.router, prefix="/v1")
app.include_router(account.router, prefix="/v1")
app.include_router(watchlist.router, prefix="/v1")
app.include_router(portfolio.router, prefix="/v1")
app.include_router(search.router, prefix="/v1")
app.include_router(chart_data.router, prefix="/v1")
app.include_router(strategy_breakdown.router, prefix="/v1")
app.include_router(notifications.router, prefix="/v1")
app.include_router(sidecars.router)
app.include_router(signal_ingest.router, prefix="/v1")
app.include_router(trades.router, prefix="/v1")
app.include_router(tradingagents_submit.router)
app.include_router(tradingagents_webhook.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "public-api",
        "version": settings.version,
        "python": "3.13",
    }


@app.get("/metrics", response_model=None)
async def metrics_endpoint(
    format: Literal["json", "prometheus"] = Query(default="json"),
):
    if format == "prometheus":
        return PlainTextResponse(metrics.prometheus_text("stock_signal_public"))
    return metrics.snapshot()
