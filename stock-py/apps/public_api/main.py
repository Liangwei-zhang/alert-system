from __future__ import annotations

from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from apps.public_api.routers import (
    account,
    auth,
    notifications,
    portfolio,
    search,
    sidecars,
    signal_ingest,
    trades,
    tradingagents_submit,
    tradingagents_webhook,
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
from infra.observability.metrics import get_metrics_registry
from infra.observability.tracing import configure_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_tracing("public-api")
    app.state.webhook_secret = settings.tradingagents_webhook_secret
    yield
    await close_redis()
    await get_http_client_factory().aclose()
    await dispose_engine()


settings = get_settings()
metrics = get_metrics_registry()

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
    allow_origins=settings.allowed_origins,
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

    try:
        response = await call_next(request)
    finally:
        duration_ms = (perf_counter() - start_time) * 1000
        metrics.counter("http_requests_total", "Total public API requests").inc()
        metrics.histogram(
            "http_request_duration_ms",
            "Public API request latency in milliseconds",
        ).observe(duration_ms)
        reset_request_context(token)

    response.headers["X-Request-ID"] = context.request_id
    return response


app.include_router(health_router)
app.include_router(auth.router, prefix="/v1")
app.include_router(account.router, prefix="/v1")
app.include_router(watchlist.router, prefix="/v1")
app.include_router(portfolio.router, prefix="/v1")
app.include_router(search.router, prefix="/v1")
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


@app.get("/metrics")
async def metrics_endpoint() -> dict:
    return metrics.snapshot()
