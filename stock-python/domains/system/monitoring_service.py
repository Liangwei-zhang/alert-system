"""
Monitoring service for Celery task and system health metrics.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

from celery import Celery
from celery.app.control import Inspect
from celery.result import AsyncResult

from infra.config import settings


class MonitoringService:
    """Service for monitoring Celery tasks and system health."""

    def __init__(self, celery_app: Celery = None):
        self.celery_app = celery_app
        self._inspect = None

    @property
    def inspect(self) -> Inspect:
        """Lazy-load Celery Inspect."""
        if self._inspect is None and self.celery_app:
            self._inspect = Inspect(app=self.celery_app)
        return self._inspect

    # ============== Worker Status ==============

    def get_worker_stats(self) -> Dict[str, Any]:
        """Get worker statistics."""
        if not self.celery_app:
            return {"error": "Celery app not initialized"}

        try:
            stats = self.inspect.stats()
            if not stats:
                return {"workers": [], "message": "No workers available"}

            worker_data = []
            for worker_name, worker_stats in stats.items():
                worker_data.append({
                    "name": worker_name,
                    "status": "active",
                    "pool": worker_stats.get("pool", {}),
                    "consumer": worker_stats.get("consumer", {}),
                    "prefetch_multiplier": worker_stats.get("prefetch_multiplier"),
                    "max_tasks_per_child": worker_stats.get("max_tasks_per_child"),
                    "stats": worker_stats.get("stats", {}),
                })

            return {
                "workers": worker_data,
                "total_workers": len(worker_data),
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            return {"error": str(e), "workers": []}

    def get_active_workers(self) -> List[str]:
        """Get list of active worker names."""
        if not self.celery_app:
            return []

        try:
            stats = self.inspect.stats()
            return list(stats.keys()) if stats else []
        except Exception:
            return []

    def get_worker_status(self) -> Dict[str, Any]:
        """Get worker ping status."""
        if not self.celery_app:
            return {"error": "Celery app not initialized"}

        try:
            ping = self.inspect.ping()
            if not ping:
                return {"workers": {}, "message": "No workers responding"}

            worker_data = {}
            for worker_name, response in ping.items():
                worker_data[worker_name] = {
                    "status": "online" if response.get("ok") == "pong" else "offline",
                    "responded_at": datetime.utcnow().isoformat(),
                }

            return {
                "workers": worker_data,
                "total_online": sum(1 for w in worker_data.values() if w["status"] == "online"),
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            return {"error": str(e), "workers": {}}

    # ============== Queue Status ==============

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        if not self.celery_app:
            return {"error": "Celery app not initialized"}

        try:
            # Get active tasks (running)
            active = self.inspect.active()
            
            # Get scheduled tasks
            scheduled = self.inspect.scheduled()
            
            # Get reserved tasks
            reserved = self.inspect.reserved()

            # Get registered tasks
            registered = self.inspect.registered()

            # Calculate totals
            running_count = sum(len(tasks) for tasks in active.values()) if active else 0
            scheduled_count = sum(len(tasks) for tasks in scheduled.values()) if scheduled else 0
            reserved_count = sum(len(tasks) for tasks in reserved.values()) if reserved else 0

            # Build queue data
            queues = {}
            
            # Combine all task info
            all_tasks = {}
            if active:
                for worker, tasks in active.items():
                    for task in tasks:
                        task_id = task.get("id", "unknown")
                        all_tasks[task_id] = {
                            "id": task_id,
                            "name": task.get("name", "unknown"),
                            "status": "running",
                            "worker": worker,
                            "started_at": task.get("time_start"),
                        }

            if scheduled:
                for worker, tasks in scheduled.items():
                    for task in tasks:
                        task_id = task.get("id", "unknown")
                        all_tasks[task_id] = {
                            "id": task_id,
                            "name": task.get("name", "unknown"),
                            "status": "pending",
                            "worker": worker,
                            "eta": task.get("eta"),
                            "priority": task.get("priority"),
                        }

            if reserved:
                for worker, tasks in reserved.items():
                    for task in tasks:
                        task_id = task.get("id", "unknown")
                        if task_id not in all_tasks:
                            all_tasks[task_id] = {
                                "id": task_id,
                                "name": task.get("name", "unknown"),
                                "status": "reserved",
                                "worker": worker,
                            }

            return {
                "queues": queues,
                "tasks": all_tasks,
                "summary": {
                    "running": running_count,
                    "scheduled": scheduled_count,
                    "reserved": reserved_count,
                    "total_active": running_count + scheduled_count + reserved_count,
                },
                "registered_tasks": list(registered.keys()) if registered else [],
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            return {"error": str(e)}

    def get_pending_tasks(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get pending tasks."""
        if not self.celery_app:
            return []

        try:
            scheduled = self.inspect.scheduled()
            reserved = self.inspect.reserved()

            pending = []
            
            if scheduled:
                for worker, tasks in scheduled.items():
                    for task in tasks:
                        pending.append({
                            "id": task.get("id"),
                            "name": task.get("name"),
                            "status": "pending",
                            "eta": task.get("eta"),
                            "priority": task.get("priority"),
                            "worker": worker,
                        })

            if reserved:
                for worker, tasks in reserved.items():
                    for task in tasks:
                        pending.append({
                            "id": task.get("id"),
                            "name": task.get("name"),
                            "status": "reserved",
                            "worker": worker,
                        })

            return pending[:limit]
        except Exception:
            return []

    def get_running_tasks(self) -> List[Dict[str, Any]]:
        """Get currently running tasks."""
        if not self.celery_app:
            return []

        try:
            active = self.inspect.active()
            if not active:
                return []

            running = []
            for worker, tasks in active.items():
                for task in tasks:
                    running.append({
                        "id": task.get("id"),
                        "name": task.get("name"),
                        "status": "running",
                        "worker": worker,
                        "started_at": task.get("time_start"),
                    })

            return running
        except Exception:
            return []

    # ============== Task Status ==============

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a specific task."""
        if not self.celery_app:
            return {"error": "Celery app not initialized"}

        try:
            result = AsyncResult(task_id, app=self.celery_app)
            
            state = result.state
            info = result.info
            
            status_map = {
                "PENDING": "pending",
                "STARTED": "started",
                "SUCCESS": "completed",
                "FAILURE": "failed",
                "RETRY": "retrying",
                "REVOKED": "revoked",
            }

            response = {
                "task_id": task_id,
                "status": status_map.get(state, state.lower()),
                "state": state,
                "ready": result.ready(),
                "successful": result.successful(),
                "traceback": info.get("traceback") if isinstance(info, dict) else None,
                "result": info if not isinstance(info, dict) else None,
            }

            # Add timing info if available
            if isinstance(info, dict):
                if "runtime" in info:
                    response["runtime_seconds"] = info["runtime"]
                if "eta" in info:
                    response["eta"] = info["eta"]
                if "expires" in info:
                    response["expires"] = info["expires"]

            return response
        except Exception as e:
            return {"error": str(e), "task_id": task_id}

    def get_task_result(self, task_id: str) -> Optional[Any]:
        """Get result of a completed task."""
        if not self.celery_app:
            return None

        try:
            result = AsyncResult(task_id, app=self.celery_app)
            if result.ready():
                return result.result
            return None
        except Exception:
            return None

    # ============== Task History (from DB) ==============

    def get_task_stats_from_backend(self) -> Dict[str, Any]:
        """Get task statistics from result backend."""
        if not self.celery_app:
            return {"error": "Celery app not initialized"}

        try:
            # Use inspect to get various stats
            stats = self.inspect.stats()
            active = self.inspect.active()
            scheduled = self.inspect.scheduled()
            reserved = self.inspect.reserved()
            revoked = self.inspect.revoked()
            confirmed = self.inspect.confirmed()

            return {
                "workers": len(stats) if stats else 0,
                "active_tasks": sum(len(tasks) for tasks in active.values()) if active else 0,
                "scheduled_tasks": sum(len(tasks) for tasks in scheduled.values()) if scheduled else 0,
                "reserved_tasks": sum(len(tasks) for tasks in reserved.values()) if reserved else 0,
                "revoked_tasks": len(revoked) if revoked else 0,
                "confirmed_tasks": len(confirmed) if confirmed else 0,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            return {"error": str(e)}

    # ============== System Health ==============

    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        health = {
            "status": "healthy",
            "celery": "unknown",
            "workers": "unknown",
            "queue": "unknown",
            "timestamp": datetime.utcnow().isoformat(),
            "details": {},
        }

        # Check Celery connection
        try:
            ping = self.inspect.ping()
            if ping:
                health["celery"] = "connected"
                health["details"]["ping"] = list(ping.keys())
            else:
                health["celery"] = "no_workers"
                health["status"] = "degraded"
        except Exception as e:
            health["celery"] = "error"
            health["details"]["error"] = str(e)
            health["status"] = "unhealthy"

        # Check workers
        try:
            stats = self.inspect.stats()
            if stats:
                health["workers"] = "active"
                health["details"]["worker_count"] = len(stats)
            else:
                health["workers"] = "no_workers"
                health["status"] = "degraded"
        except Exception as e:
            health["workers"] = "error"
            health["details"]["worker_error"] = str(e)
            health["status"] = "unhealthy"

        # Check queue
        try:
            scheduled = self.inspect.scheduled()
            reserved = self.inspect.reserved()
            total = 0
            if scheduled:
                total += sum(len(tasks) for tasks in scheduled.values())
            if reserved:
                total += sum(len(tasks) for tasks in reserved.values())
            
            health["queue"] = "ok"
            health["details"]["pending_tasks"] = total
        except Exception as e:
            health["queue"] = "error"
            health["details"]["queue_error"] = str(e)

        return health

    # ============== Combined Dashboard Data ==============

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get combined data for dashboard display."""
        return {
            "health": self.get_system_health(),
            "workers": self.get_worker_status(),
            "queues": self.get_queue_stats(),
            "stats": self.get_task_stats_from_backend(),
        }


# Singleton instance
monitoring_service = MonitoringService()
