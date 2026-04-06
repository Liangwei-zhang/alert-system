"""
Health check endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from domains.system.health_service import HealthService, get_health_service
from infra.database import get_db

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check."""
    return {"status": "healthy", "service": "stock-api"}


@router.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness check with database connectivity."""
    health_service = HealthService(db)
    db_health = await health_service.check_database()
    
    return {
        "status": "ready" if db_health["status"] == "healthy" else "not_ready",
        "database": db_health["status"],
    }


@router.get("/health/live")
async def liveness_check():
    """Liveness check."""
    return {"status": "alive"}


@router.get("/health/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_db)):
    """Detailed health check with all service statuses."""
    health_service = HealthService(db)
    return await health_service.get_overall_health()