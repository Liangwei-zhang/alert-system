"""
Runtime stats and metrics endpoints.
"""
from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from domains.system.runtime_status_service import RuntimeStatusService, get_runtime_status_service
from domains.system.health_service import HealthService, get_health_service
from infra.database import get_db

router = APIRouter()


# ============== Request/Response Models ==============

class MetricRecordRequest(BaseModel):
    metric_name: str
    value: float
    metric_type: str = "gauge"
    labels: Optional[dict] = None


class ConfigSetRequest(BaseModel):
    key: str
    value: str
    value_type: str = "string"
    description: Optional[str] = None
    is_secret: bool = False


# ============== Metrics Endpoints ==============

@router.get("/metrics")
async def get_metrics(
    metric_name: str,
    since: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Get metrics history for a specific metric."""
    service = await get_runtime_status_service(db)
    
    since_dt = None
    if since:
        since_dt = datetime.fromisoformat(since)
    
    metrics = await service.get_metric(metric_name, since=since_dt, limit=limit)
    
    return {
        "metric_name": metric_name,
        "count": len(metrics),
        "metrics": [
            {
                "id": m.id,
                "value": m.value,
                "labels": m.labels,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in metrics
        ],
    }


@router.get("/metrics/latest")
async def get_latest_metric(
    metric_name: str,
    db: AsyncSession = Depends(get_db)
):
    """Get the latest value for a metric."""
    service = await get_runtime_status_service(db)
    metric = await service.get_latest_metric(metric_name)
    
    if not metric:
        return {"error": "No data found", "metric_name": metric_name}
    
    return {
        "metric_name": metric_name,
        "value": metric.value,
        "labels": metric.labels,
        "timestamp": metric.timestamp.isoformat(),
    }


@router.get("/metrics/aggregates")
async def get_metric_aggregates(
    metric_name: str,
    interval_minutes: int = 5,
    hours: int = 1,
    db: AsyncSession = Depends(get_db)
):
    """Get aggregated metrics (avg, min, max, count)."""
    service = await get_runtime_status_service(db)
    
    since = datetime.utcnow() - timedelta(hours=hours)
    aggregates = await service.get_metric_aggregates(
        metric_name, 
        interval_minutes=interval_minutes,
        since=since
    )
    
    return {
        "metric_name": metric_name,
        "interval_minutes": interval_minutes,
        "aggregates": aggregates,
    }


@router.post("/metrics")
async def record_metric(
    request: MetricRecordRequest,
    db: AsyncSession = Depends(get_db)
):
    """Record a new metric value."""
    service = await get_runtime_status_service(db)
    success = await service.record_metric(
        request.metric_name,
        request.value,
        request.metric_type,
        request.labels
    )
    
    return {
        "success": success,
        "metric_name": request.metric_name,
        "value": request.value,
    }


# ============== Configuration Endpoints ==============

@router.get("/config")
async def get_all_config(
    db: AsyncSession = Depends(get_db)
):
    """Get all system configurations."""
    service = await get_runtime_status_service(db)
    configs = await service.get_all_configs()
    
    return {
        "configs": [
            {
                "key": c.key,
                "value": "***" if c.is_secret else c.value,
                "value_type": c.value_type,
                "description": c.description,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in configs
        ],
    }


@router.get("/config/{key}")
async def get_config(
    key: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific configuration value."""
    service = await get_runtime_status_service(db)
    config = await service.get_config(key)
    
    if not config:
        return {"error": "Config not found", "key": key}
    
    return {
        "key": config.key,
        "value": "***" if config.is_secret else config.value,
        "value_type": config.value_type,
        "description": config.description,
        "is_secret": config.is_secret,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


@router.post("/config")
async def set_config(
    request: ConfigSetRequest,
    db: AsyncSession = Depends(get_db)
):
    """Set a system configuration value."""
    service = await get_runtime_status_service(db)
    success = await service.set_config(
        request.key,
        request.value,
        request.value_type,
        request.description,
        request.is_secret,
        updated_by="admin_api"
    )
    
    return {
        "success": success,
        "key": request.key,
    }


# ============== Runtime Summary ==============

@router.get("/runtime/summary")
async def get_runtime_summary(
    db: AsyncSession = Depends(get_db)
):
    """Get runtime status summary."""
    service = await get_runtime_status_service(db)
    return await service.get_runtime_summary()


@router.get("/runtime/status")
async def get_runtime_status(
    db: AsyncSession = Depends(get_db)
):
    """Get overall runtime status."""
    health_service = await get_health_service(db)
    return await health_service.get_overall_health()