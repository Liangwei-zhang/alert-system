from __future__ import annotations

from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from apps.admin_api.routers import (
    acceptance,
    analytics,
    anomalies,
    audit,
    backtests,
    distribution,
    operators,
    runtime_monitoring,
    scanner,
    signal_stats,
    tasks,
    tradingagents,
    users,
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
from infra.security.auth import require_admin


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_tracing("admin-api")
    yield
    await close_redis()
    await get_http_client_factory().aclose()
    await dispose_engine()


settings = get_settings()
metrics = get_metrics_registry()

app = FastAPI(
    title=f"{settings.project_name} Admin API",
    version=settings.version,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    dependencies=[Depends(require_admin)],
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
        metrics.counter("admin_http_requests_total", "Total admin API requests").inc()
        metrics.histogram(
            "admin_http_request_duration_ms",
            "Admin API request latency in milliseconds",
        ).observe(duration_ms)
        reset_request_context(token)

    response.headers["X-Request-ID"] = context.request_id
    return response


app.include_router(health_router)
app.include_router(acceptance.router)
app.include_router(anomalies.router)
app.include_router(analytics.router)
app.include_router(audit.router)
app.include_router(backtests.router)
app.include_router(distribution.router)
app.include_router(operators.router)
app.include_router(runtime_monitoring.router)
app.include_router(scanner.router)
app.include_router(signal_stats.router)
app.include_router(tasks.router)
app.include_router(tradingagents.router)
app.include_router(users.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "admin-api",
        "version": settings.version,
        "python": "3.13",
    }


@app.get("/metrics")
async def metrics_endpoint() -> dict:
    return metrics.snapshot()
