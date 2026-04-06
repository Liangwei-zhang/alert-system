"""
FastAPI application entry point.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from apps.public_api.routers import auth, health, websocket, portfolio, stocks, signals, notifications, webpush
from infra.security.audit import AuditMiddleware
from infra.cache import cache
from infra.config import settings
from infra.database import engine
from infra.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    setup_logging()
    await cache.connect()
    yield
    # Shutdown
    await cache.disconnect()
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Static files
static_path = "/app/static"
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

# Subscription page
@app.get("/subscription.html")
async def subscription():
    static_file = os.path.join(static_path, "subscription.html")
    if os.path.exists(static_file):
        return FileResponse(static_file)
    return {"error": "Not found"}

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(websocket.router, prefix="/api/v1", tags=["websocket"])
app.include_router(stocks.router, prefix="/api/v1", tags=["stocks"])
app.include_router(portfolio.router, prefix="/api/v1", tags=["portfolio"])
app.include_router(signals.router, prefix="/api/v1", tags=["signals"])
app.include_router(notifications.router, prefix="/api/v1", tags=["notifications"])
app.include_router(webpush.router, prefix="/api/v1", tags=["webpush"])

# Audit middleware
app.add_middleware(AuditMiddleware)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Stock API v1", "docs": "/docs" if settings.DEBUG else "disabled"}