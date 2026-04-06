"""
Health check service for system health monitoring.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.models.system import SystemConfigModel, RuntimeMetricModel


class HealthService:
    """Service for system health checks."""

    # Health status thresholds
    CRITICAL_THRESHOLD = 0
    WARNING_THRESHOLD = 1

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_database(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            # Simple query to verify connection
            result = await self.db.execute(select(1))
            return {
                "status": "healthy",
                "message": "Database connection OK",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Database error: {str(e)}",
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def check_redis(self) -> Dict[str, Any]:
        """Check Redis connectivity."""
        # TODO: Implement Redis health check
        return {
            "status": "unknown",
            "message": "Redis check not implemented",
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def check_celery(self) -> Dict[str, Any]:
        """Check Celery connectivity."""
        # TODO: Implement Celery health check
        return {
            "status": "unknown",
            "message": "Celery check not implemented",
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def get_overall_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        checks = {
            "database": await self.check_database(),
            "redis": await self.check_redis(),
            "celery": await self.check_celery(),
        }

        # Determine overall status
        statuses = [check["status"] for check in checks.values()]
        
        if "unhealthy" in statuses:
            overall_status = "unhealthy"
        elif "degraded" in statuses:
            overall_status = "degraded"
        elif "unknown" in statuses:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks,
        }

    async def get_service_status(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific service."""
        checks = await self.get_overall_health()
        return checks.get("checks", {}).get(service_name)

    async def record_metric(
        self, 
        metric_name: str, 
        value: float, 
        metric_type: str = "gauge",
        labels: Optional[Dict[str, str]] = None
    ) -> bool:
        """Record a runtime metric."""
        try:
            metric = RuntimeMetricModel(
                metric_name=metric_name,
                metric_type=metric_type,
                value=value,
                labels=labels or {},
                timestamp=datetime.utcnow(),
            )
            self.db.add(metric)
            await self.db.commit()
            return True
        except Exception:
            await self.db.rollback()
            return False

    async def get_recent_metrics(
        self, 
        metric_name: str, 
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> List[RuntimeMetricModel]:
        """Get recent metrics for a given metric name."""
        query = select(RuntimeMetricModel).where(
            RuntimeMetricModel.metric_name == metric_name
        )
        
        if since:
            query = query.where(RuntimeMetricModel.timestamp >= since)
        
        query = query.order_by(RuntimeMetricModel.timestamp.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())


async def get_health_service(db: AsyncSession) -> HealthService:
    """Dependency injection for HealthService."""
    return HealthService(db)