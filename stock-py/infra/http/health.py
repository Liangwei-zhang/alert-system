from __future__ import annotations

import asyncio

from fastapi import APIRouter
from sqlalchemy import text

from infra.analytics.clickhouse_client import get_clickhouse_client
from infra.cache.redis_client import get_redis
from infra.core.config import get_settings
from infra.db.session import get_session_factory
from infra.storage.object_storage import get_object_storage_client

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "stock-py-api"}


@router.get("/health/ready")
async def readiness_check() -> dict[str, object]:
    settings = get_settings()

    async def check_database() -> dict[str, object]:
        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))
            return {"status": "healthy"}
        except Exception as exc:
            return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}

    async def check_redis() -> dict[str, object]:
        try:
            client = await get_redis()
            await client.ping()
            return {"status": "healthy"}
        except Exception as exc:
            return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}

    async def check_clickhouse() -> dict[str, object]:
        if settings.analytics_backend != "clickhouse":
            return {"status": "skipped", "backend": settings.analytics_backend}
        try:
            payload = await get_clickhouse_client().ping()
            return {"status": "healthy", **payload}
        except Exception as exc:
            return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}

    async def check_object_storage() -> dict[str, object]:
        if settings.object_storage_backend != "s3":
            return {"status": "skipped", "backend": settings.object_storage_backend}
        try:
            payload = await get_object_storage_client().ping()
            return {"status": "healthy", **payload}
        except Exception as exc:
            return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}

    database, redis, clickhouse, object_storage = await asyncio.gather(
        check_database(),
        check_redis(),
        check_clickhouse(),
        check_object_storage(),
    )
    dependencies = {
        "database": database,
        "redis": redis,
        "clickhouse": clickhouse,
        "object_storage": object_storage,
    }
    ready = all(
        payload.get("status") in {"healthy", "skipped"} for payload in dependencies.values()
    )
    return {
        "status": "ready" if ready else "degraded",
        "dependencies": dependencies,
    }


@router.get("/health/live")
async def liveness_check() -> dict[str, str]:
    return {"status": "alive"}
