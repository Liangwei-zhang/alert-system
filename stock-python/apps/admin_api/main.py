"""
FastAPI Admin API application entry point.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.admin_api.routers import (
    admin, admin_audit, admin_stats, admin_subscription, admin_tasks, runtime
)
from infra.security.audit import AuditMiddleware
from infra.cache import cache
from infra.config import settings
from infra.database import engine
from infra.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    setup_logging()
    await cache.connect()
    yield
    await cache.disconnect()
    await engine.dispose()


app = FastAPI(
    title=f"{settings.PROJECT_NAME} - Admin API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AuditMiddleware)

app.include_router(runtime.router, prefix="/api/v1/runtime", tags=["Runtime"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(admin_audit.router, prefix="/api/v1/admin/audit", tags=["Admin Audit"])
app.include_router(admin_stats.router, prefix="/api/v1/admin/stats", tags=["Admin Stats"])
app.include_router(admin_subscription.router, prefix="/api/v1/admin/subscriptions", tags=["Admin Subscriptions"])
app.include_router(admin_tasks.router, prefix="/api/v1/admin/tasks", tags=["Admin Tasks"])