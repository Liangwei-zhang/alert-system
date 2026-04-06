"""
Runtime status service for monitoring system metrics and status.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.models.system import RuntimeMetricModel, SystemConfigModel


class RuntimeStatusService:
    """Service for runtime status and metrics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============== System Metrics ==============

    async def record_metric(
        self,
        metric_name: str,
        value: float,
        metric_type: str = "gauge",
        labels: Optional[Dict[str, str]] = None
    ) -> bool:
        """Record a metric value."""
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

    async def get_metric(
        self,
        metric_name: str,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[RuntimeMetricModel]:
        """Get metric history."""
        query = select(RuntimeMetricModel).where(
            RuntimeMetricModel.metric_name == metric_name
        )
        
        if since:
            query = query.where(RuntimeMetricModel.timestamp >= since)
        
        query = query.order_by(RuntimeMetricModel.timestamp.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_latest_metric(self, metric_name: str) -> Optional[RuntimeMetricModel]:
        """Get the latest value for a metric."""
        query = select(RuntimeMetricModel).where(
            RuntimeMetricModel.metric_name == metric_name
        ).order_by(RuntimeMetricModel.timestamp.desc()).limit(1)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_metric_aggregates(
        self,
        metric_name: str,
        interval_minutes: int = 5,
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get aggregated metrics (avg, min, max, count) over intervals."""
        if since is None:
            since = datetime.utcnow() - timedelta(hours=1)

        # This is a simplified version - in production you'd use window functions
        metrics = await self.get_metric(metric_name, since=since, limit=1000)
        
        if not metrics:
            return []

        # Group by time intervals
        intervals = {}
        for metric in metrics:
            # Round to nearest interval
            minute = (metric.timestamp.minute // interval_minutes) * interval_minutes
            key = metric.timestamp.replace(minute=minute, second=0, microsecond=0)
            
            if key not in intervals:
                intervals[key] = []
            intervals[key].append(metric.value)

        # Calculate aggregates
        result = []
        for timestamp, values in sorted(intervals.items()):
            result.append({
                "timestamp": timestamp.isoformat(),
                "avg": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "count": len(values),
            })

        return result

    # ============== System Configuration ==============

    async def get_config(self, key: str) -> Optional[SystemConfigModel]:
        """Get a system configuration value."""
        query = select(SystemConfigModel).where(SystemConfigModel.key == key)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get parsed configuration value."""
        config = await self.get_config(key)
        if not config:
            return default
        
        # Parse based on type
        if config.value_type == "int":
            return int(config.value) if config.value else default
        elif config.value_type == "float":
            return float(config.value) if config.value else default
        elif config.value_type == "bool":
            return config.value.lower() in ("true", "1", "yes") if config.value else default
        elif config.value_type == "json":
            import json
            return json.loads(config.value) if config.value else default
        else:
            return config.value

    async def set_config(
        self,
        key: str,
        value: Any,
        value_type: str = "string",
        description: Optional[str] = None,
        is_secret: bool = False,
        updated_by: Optional[str] = None
    ) -> bool:
        """Set a system configuration value."""
        try:
            config = await self.get_config(key)
            
            import json
            if value_type == "json":
                str_value = json.dumps(value)
            else:
                str_value = str(value)

            if config:
                config.value = str_value
                config.value_type = value_type
                config.description = description
                config.is_secret = is_secret
                config.updated_at = datetime.utcnow()
                config.updated_by = updated_by
            else:
                config = SystemConfigModel(
                    key=key,
                    value=str_value,
                    value_type=value_type,
                    description=description,
                    is_secret=is_secret,
                    updated_by=updated_by,
                )
                self.db.add(config)

            await self.db.commit()
            return True
        except Exception:
            await self.db.rollback()
            return False

    async def get_all_configs(self) -> List[SystemConfigModel]:
        """Get all system configurations."""
        query = select(SystemConfigModel).order_by(SystemConfigModel.key)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    # ============== Runtime Status Summary ==============

    async def get_runtime_summary(self) -> Dict[str, Any]:
        """Get summary of runtime status."""
        now = datetime.utcnow()
        since = now - timedelta(hours=1)

        # Get recent metrics
        active_users_query = select(func.count(RuntimeMetricModel.id)).where(
            RuntimeMetricModel.metric_name == "active_users",
            RuntimeMetricModel.timestamp >= since
        )
        active_users_result = await self.db.execute(active_users_query)
        active_users_count = active_users_result.scalar() or 0

        # Get latest system metrics
        uptime_metric = await self.get_latest_metric("system_uptime")
        cpu_metric = await self.get_latest_metric("system_cpu")
        memory_metric = await self.get_latest_metric("system_memory")

        return {
            "timestamp": now.isoformat(),
            "metrics": {
                "active_users": active_users_count,
                "uptime_seconds": uptime_metric.value if uptime_metric else None,
                "cpu_percent": cpu_metric.value if cpu_metric else None,
                "memory_percent": memory_metric.value if memory_metric else None,
            },
            "config": await self.get_all_configs(),
        }


async def get_runtime_status_service(db: AsyncSession) -> RuntimeStatusService:
    """Dependency injection for RuntimeStatusService."""
    return RuntimeStatusService(db)