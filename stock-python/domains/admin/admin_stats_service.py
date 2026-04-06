"""
Admin statistics service for operational monitoring.

Provides comprehensive system stats including:
- User and subscription metrics
- Signal distribution stats
- Celery task queue status
- System health metrics
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import psutil
import platform

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from domains.auth.user import User
from domains.signals.signal import Signal, SignalStatus
from domains.subscription.subscription import Subscription, SubscriptionTier, SubscriptionStatus
from domains.search.stock import Stock
from domains.portfolio.portfolio import Portfolio
from domains.tradingagents.strategy import Strategy
from domains.notifications.notification import Notification, NotificationStatus


class AdminStatsService:
    """Service for admin operational statistics."""

    def __init__(self, db: Session):
        self.db = db

    # ============== User & Subscription Stats ==============

    def get_user_stats(self) -> Dict[str, Any]:
        """Get user statistics."""
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        last_30d = now - timedelta(days=30)

        total = self.db.execute(select(func.count(User.id))).scalar()
        active = self.db.execute(
            select(func.count(User.id)).where(User.is_active == True)
        ).scalar()
        new_24h = self.db.execute(
            select(func.count(User.id)).where(User.created_at >= last_24h)
        ).scalar()
        new_7d = self.db.execute(
            select(func.count(User.id)).where(User.created_at >= last_7d)
        ).scalar()
        new_30d = self.db.execute(
            select(func.count(User.id)).where(User.created_at >= last_30d)
        ).scalar()

        return {
            "total": total,
            "active": active,
            "inactive": total - active,
            "new_24h": new_24h,
            "new_7d": new_7d,
            "new_30d": new_30d,
        }

    def get_subscription_stats(self) -> Dict[str, Any]:
        """Get subscription statistics."""
        total = self.db.execute(select(func.count(Subscription.id))).scalar()
        active = self.db.execute(
            select(func.count(Subscription.id)).where(
                Subscription.status == SubscriptionStatus.ACTIVE
            )
        ).scalar()
        trial = self.db.execute(
            select(func.count(Subscription.id)).where(
                Subscription.is_trial == True
            )
        ).scalar()
        past_due = self.db.execute(
            select(func.count(Subscription.id)).where(
                Subscription.status == SubscriptionStatus.PAST_DUE
            )
        ).scalar()
        canceled = self.db.execute(
            select(func.count(Subscription.id)).where(
                Subscription.status == SubscriptionStatus.CANCELED
            )
        ).scalar()

        # Tier breakdown
        by_tier = {}
        for tier in SubscriptionTier:
            count = self.db.execute(
                select(func.count(Subscription.id)).where(
                    Subscription.tier == tier
                )
            ).scalar()
            by_tier[tier.value] = count

        return {
            "total": total,
            "active": active,
            "trial": trial,
            "past_due": past_due,
            "canceled": canceled,
            "by_tier": by_tier,
        }

    # ============== Signal Stats ==============

    def get_signal_stats(self) -> Dict[str, Any]:
        """Get signal statistics."""
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        last_30d = now - timedelta(days=30)

        total = self.db.execute(select(func.count(Signal.id))).scalar()
        
        # Status breakdown
        status_counts = {}
        for status in SignalStatus:
            count = self.db.execute(
                select(func.count(Signal.id)).where(Signal.status == status)
            ).scalar()
            status_counts[status.value] = count

        generated_24h = self.db.execute(
            select(func.count(Signal.id)).where(Signal.generated_at >= last_24h)
        ).scalar()
        generated_7d = self.db.execute(
            select(func.count(Signal.id)).where(Signal.generated_at >= last_7d)
        ).scalar()
        generated_30d = self.db.execute(
            select(func.count(Signal.id)).where(Signal.generated_at >= last_30d)
        ).scalar()

        triggered_24h = self.db.execute(
            select(func.count(Signal.id)).where(
                Signal.status == SignalStatus.TRIGGERED,
                Signal.triggered_at >= last_24h
            )
        ).scalar()

        return {
            "total": total,
            "by_status": status_counts,
            "generated_24h": generated_24h,
            "generated_7d": generated_7d,
            "generated_30d": generated_30d,
            "triggered_24h": triggered_24h,
        }

    def get_signal_distribution_stats(self) -> Dict[str, Any]:
        """Get signal distribution by type, direction, and source."""
        # By signal type
        type_counts = {}
        self.db.execute(
            select(Signal.signal_type, func.count(Signal.id))
            .group_by(Signal.signal_type)
        ).all()
        
        # Get all signals for distribution analysis
        signals = self.db.execute(
            select(Signal.signal_type, Signal.direction, Signal.source)
        ).scalars().all()

        type_dist = {}
        direction_dist = {}
        source_dist = {}

        for s in signals:
            type_dist[s.signal_type] = type_dist.get(s.signal_type, 0) + 1
            direction_dist[s.direction] = direction_dist.get(s.direction, 0) + 1
            source_dist[s.source] = source_dist.get(s.source, 0) + 1

        return {
            "by_type": type_dist,
            "by_direction": direction_dist,
            "by_source": source_dist,
        }

    # ============== Celery Task Queue Status ==============

    def get_celery_status(self) -> Dict[str, Any]:
        """Get Celery task queue status."""
        try:
            from celery import current_app
            inspector = current_app.control.inspect()
            
            # Get active workers
            active_workers = inspector.active() or {}
            worker_count = len(active_workers)
            worker_list = list(active_workers.keys())

            # Get scheduled/queued tasks
            scheduled = inspector.scheduled() or {}
            queued_count = sum(len(tasks) for tasks in scheduled.values())

            # Get reserved tasks
            reserved = inspector.reserved() or {}
            reserved_count = sum(len(tasks) for tasks in reserved.values())

            # Get stats
            stats = inspector.stats() or {}

            # Build active task list
            active_tasks = []
            for worker, tasks in active_workers.items():
                for task in tasks:
                    active_tasks.append({
                        "id": task.get("id"),
                        "name": task.get("name"),
                        "worker": worker,
                        "status": "started",
                        "started_at": task.get("time_start"),
                    })

            return {
                "status": "connected",
                "active_workers": worker_count,
                "worker_list": worker_list,
                "active_tasks": len(active_tasks),
                "queued_tasks": queued_count,
                "reserved_tasks": reserved_count,
                "tasks": active_tasks,
                "workers_detail": {
                    worker: {
                        "status": "online",
                        "pool": stats.get(worker, {}).get("pool", {}).get("max", "unknown"),
                    }
                    for worker in worker_list
                },
            }
        except Exception as e:
            return self._get_celery_status_fallback(str(e))

    def _get_celery_status_fallback(self, error: str) -> Dict[str, Any]:
        """Fallback Celery status using Redis directly."""
        try:
            import redis
            from infra.config import settings
            
            r = redis.from_url(settings.REDIS_URL)
            
            # Try to get Celery info from Redis
            info = r.info("clients")
            
            return {
                "status": "limited",
                "error": error,
                "redis_connected": True,
                "active_workers": 0,
                "active_tasks": 0,
                "queued_tasks": 0,
                "tasks": [],
            }
        except Exception:
            return {
                "status": "unavailable",
                "error": str(error),
                "redis_connected": False,
                "active_workers": 0,
                "active_tasks": 0,
                "queued_tasks": 0,
                "tasks": [],
            }

    # ============== System Health Metrics ==============

    def get_system_health(self) -> Dict[str, Any]:
        """Get system health metrics."""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            
            # Memory
            memory = psutil.virtual_memory()
            
            # Disk
            disk = psutil.disk_usage('/')
            
            # Network
            net_io = psutil.net_io_counters()
            
            # Process info
            process = psutil.Process()
            process_info = {
                "pid": process.pid,
                "threads": process.num_threads(),
                "memory_mb": process.memory_info().rss / 1024 / 1024,
            }

            return {
                "platform": platform.system(),
                "platform_version": platform.version(),
                "python_version": platform.python_version(),
                "cpu": {
                    "usage_percent": cpu_percent,
                    "count": cpu_count,
                },
                "memory": {
                    "total_gb": round(memory.total / 1024**3, 2),
                    "available_gb": round(memory.available / 1024**3, 2),
                    "used_gb": round(memory.used / 1024**3, 2),
                    "percent": memory.percent,
                },
                "disk": {
                    "total_gb": round(disk.total / 1024**3, 2),
                    "used_gb": round(disk.used / 1024**3, 2),
                    "free_gb": round(disk.free / 1024**3, 2),
                    "percent": disk.percent,
                },
                "network": {
                    "bytes_sent_mb": round(net_io.bytes_sent / 1024**2, 2),
                    "bytes_recv_mb": round(net_io.bytes_recv / 1024**2, 2),
                },
                "process": process_info,
                "status": "healthy" if cpu_percent < 90 and memory.percent < 90 else "warning",
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }

    # ============== Combined Stats ==============

    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get all operational stats in one call."""
        return {
            "users": self.get_user_stats(),
            "subscriptions": self.get_subscription_stats(),
            "signals": self.get_signal_stats(),
            "signals_distribution": self.get_signal_distribution_stats(),
            "celery": self.get_celery_status(),
            "system_health": self.get_system_health(),
            "stocks": {
                "total": self.db.execute(select(func.count(Stock.id))).scalar(),
                "active": self.db.execute(
                    select(func.count(Stock.id)).where(Stock.is_active == True)
                ).scalar(),
            },
            "portfolios": {
                "total": self.db.execute(select(func.count(Portfolio.id))).scalar(),
            },
            "strategies": {
                "total": self.db.execute(select(func.count(Strategy.id))).scalar(),
            },
            "notifications": {
                "pending": self.db.execute(
                    select(func.count(Notification.id)).where(
                        Notification.status == NotificationStatus.PENDING
                    )
                ).scalar(),
                "sent": self.db.execute(
                    select(func.count(Notification.id)).where(
                        Notification.status == NotificationStatus.SENT
                    )
                ).scalar(),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }