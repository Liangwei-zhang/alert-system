"""
Unit tests for MonitoringService.

Tested by: Trades Team
Original developer: System Team
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

from domains.system.monitoring_service import MonitoringService


class TestMonitoringService:
    """Test cases for MonitoringService."""

    @pytest.fixture
    def mock_celery_app(self):
        """Create mock Celery app."""
        app = MagicMock()
        app.control = MagicMock()
        app.control.inspect = MagicMock(return_value=MagicMock())
        return app

    @pytest.fixture
    def monitoring_service(self, mock_celery_app):
        """Create MonitoringService instance."""
        return MonitoringService(mock_celery_app)

    # ============== Worker Status ==============

    def test_get_worker_stats_no_celery(self):
        """Test worker stats without Celery app."""
        service = MonitoringService()
        stats = service.get_worker_stats()
        assert "error" in stats

    def test_get_worker_stats_success(self, monitoring_service, mock_celery_app):
        """Test successful worker stats retrieval."""
        mock_stats = {
            "worker1": {
                "pool": {"max": 10},
                "consumer": {},
                "prefetch_multiplier": 4,
                "max_tasks_per_child": 1000,
                "stats": {},
            }
        }
        monitoring_service.inspect.stats = MagicMock(return_value=mock_stats)

        stats = monitoring_service.get_worker_stats()

        assert "workers" in stats
        assert stats["total_workers"] == 1

    def test_get_worker_stats_no_workers(self, monitoring_service, mock_celery_app):
        """Test worker stats with no workers."""
        monitoring_service.inspect.stats = MagicMock(return_value=None)

        stats = monitoring_service.get_worker_stats()

        assert "workers" in stats
        assert stats["message"] == "No workers available"

    def test_get_active_workers(self, monitoring_service, mock_celery_app):
        """Test getting active workers list."""
        mock_stats = {"worker1": {}, "worker2": {}}
        monitoring_service.inspect.stats = MagicMock(return_value=mock_stats)

        workers = monitoring_service.get_active_workers()

        assert len(workers) == 2

    def test_get_active_workers_no_celery(self):
        """Test getting active workers without Celery app."""
        service = MonitoringService()
        workers = service.get_active_workers()
        assert workers == []

    def test_get_worker_status_success(self, monitoring_service, mock_celery_app):
        """Test getting worker status."""
        mock_ping = {"worker1": {"ok": "pong"}, "worker2": {"ok": "pong"}}
        monitoring_service.inspect.ping = MagicMock(return_value=mock_ping)

        status = monitoring_service.get_worker_status()

        assert "workers" in status
        assert status["total_online"] == 2

    def test_get_worker_status_no_workers(self, monitoring_service, mock_celery_app):
        """Test worker status with no workers."""
        monitoring_service.inspect.ping = MagicMock(return_value=None)

        status = monitoring_service.get_worker_status()

        assert status["message"] == "No workers responding"

    # ============== Queue Status ==============

    def test_get_queue_stats_success(self, monitoring_service, mock_celery_app):
        """Test getting queue statistics."""
        monitoring_service.inspect.active = MagicMock(return_value={
            "worker1": [{"id": "task1", "name": "task", "time_start": 123}]
        })
        monitoring_service.inspect.scheduled = MagicMock(return_value={})
        monitoring_service.inspect.reserved = MagicMock(return_value={})
        monitoring_service.inspect.registered = MagicMock(return_value={"task1": []})

        stats = monitoring_service.get_queue_stats()

        assert "summary" in stats
        assert "tasks" in stats

    def test_get_queue_stats_no_celery(self):
        """Test queue stats without Celery app."""
        service = MonitoringService()
        stats = service.get_queue_stats()
        assert "error" in stats

    def test_get_pending_tasks(self, monitoring_service, mock_celery_app):
        """Test getting pending tasks."""
        monitoring_service.inspect.scheduled = MagicMock(return_value={
            "worker1": [{"id": "task1", "name": "task", "eta": "2024-01-01"}]
        })
        monitoring_service.inspect.reserved = MagicMock(return_value={})

        tasks = monitoring_service.get_pending_tasks(limit=10)

        assert isinstance(tasks, list)

    def test_get_running_tasks(self, monitoring_service, mock_celery_app):
        """Test getting running tasks."""
        monitoring_service.inspect.active = MagicMock(return_value={
            "worker1": [{"id": "task1", "name": "task"}]
        })

        tasks = monitoring_service.get_running_tasks()

        assert isinstance(tasks, list)

    def test_get_running_tasks_no_celery(self):
        """Test running tasks without Celery app."""
        service = MonitoringService()
        tasks = service.get_running_tasks()
        assert tasks == []

    # ============== Task Status ==============

    def test_get_task_status(self, monitoring_service, mock_celery_app):
        """Test getting task status."""
        mock_result = MagicMock()
        mock_result.state = "SUCCESS"
        mock_result.info = {"result": "done"}
        mock_result.ready = MagicMock(return_value=True)
        mock_result.successful = MagicMock(return_value=True)

        with patch('domains.system.monitoring_service.AsyncResult', return_value=mock_result):
            status = monitoring_service.get_task_status("task123")

        assert "task_id" in status
        assert "status" in status

    def test_get_task_status_no_celery(self):
        """Test task status without Celery app."""
        service = MonitoringService()
        status = service.get_task_status("task123")
        assert "error" in status

    def test_get_task_result_ready(self, monitoring_service, mock_celery_app):
        """Test getting task result when ready."""
        mock_result = MagicMock()
        mock_result.ready = MagicMock(return_value=True)
        mock_result.result = "task result"

        with patch('domains.system.monitoring_service.AsyncResult', return_value=mock_result):
            result = monitoring_service.get_task_result("task123")

        assert result is not None

    def test_get_task_result_not_ready(self, monitoring_service, mock_celery_app):
        """Test getting task result when not ready."""
        mock_result = MagicMock()
        mock_result.ready = MagicMock(return_value=False)

        with patch('domains.system.monitoring_service.AsyncResult', return_value=mock_result):
            result = monitoring_service.get_task_result("task123")

        assert result is None

    def test_get_task_result_no_celery(self):
        """Test task result without Celery app."""
        service = MonitoringService()
        result = service.get_task_result("task123")
        assert result is None

    # ============== Task History ==============

    def test_get_task_stats_from_backend(self, monitoring_service, mock_celery_app):
        """Test getting task stats from backend."""
        monitoring_service.inspect.stats = MagicMock(return_value={"worker1": {}})
        monitoring_service.inspect.active = MagicMock(return_value={"worker1": []})
        monitoring_service.inspect.scheduled = MagicMock(return_value={})
        monitoring_service.inspect.reserved = MagicMock(return_value={})
        monitoring_service.inspect.revoked = MagicMock(return_value={})
        monitoring_service.inspect.confirmed = MagicMock(return_value={})

        stats = monitoring_service.get_task_stats_from_backend()

        assert "workers" in stats
        assert "active_tasks" in stats

    def test_get_task_stats_from_backend_no_celery(self):
        """Test task stats without Celery app."""
        service = MonitoringService()
        stats = service.get_task_stats_from_backend()
        assert "error" in stats

    # ============== System Health ==============

    def test_get_system_health_all_healthy(self, monitoring_service, mock_celery_app):
        """Test system health when all healthy."""
        monitoring_service.inspect.ping = MagicMock(return_value={"worker1": {"ok": "pong"}})
        monitoring_service.inspect.stats = MagicMock(return_value={"worker1": {}})
        monitoring_service.inspect.scheduled = MagicMock(return_value={})
        monitoring_service.inspect.reserved = MagicMock(return_value={})

        health = monitoring_service.get_system_health()

        assert health["status"] in ["healthy", "degraded"]

    def test_get_system_health_no_workers(self, monitoring_service, mock_celery_app):
        """Test system health with no workers."""
        monitoring_service.inspect.ping = MagicMock(return_value={})
        monitoring_service.inspect.stats = MagicMock(return_value=None)
        monitoring_service.inspect.scheduled = MagicMock(return_value={})
        monitoring_service.inspect.reserved = MagicMock(return_value={})

        health = monitoring_service.get_system_health()

        assert health["status"] in ["degraded", "unhealthy"]

    def test_get_system_health_no_celery(self):
        """Test system health without Celery app."""
        service = MonitoringService()
        health = service.get_system_health()
        assert health["status"] == "unhealthy"

    # ============== Dashboard Data ==============

    def test_get_dashboard_data(self, monitoring_service, mock_celery_app):
        """Test getting dashboard data."""
        monitoring_service.inspect.ping = MagicMock(return_value={})
        monitoring_service.inspect.stats = MagicMock(return_value=None)
        monitoring_service.inspect.active = MagicMock(return_value={})
        monitoring_service.inspect.scheduled = MagicMock(return_value={})
        monitoring_service.inspect.reserved = MagicMock(return_value={})
        monitoring_service.inspect.registered = MagicMock(return_value={})

        data = monitoring_service.get_dashboard_data()

        assert "health" in data
        assert "workers" in data
        assert "queues" in data

    # ============== Edge Cases ==============

    def test_get_worker_stats_exception(self, monitoring_service, mock_celery_app):
        """Test worker stats exception handling."""
        monitoring_service.inspect.stats = MagicMock(side_effect=Exception("Error"))

        stats = monitoring_service.get_worker_stats()

        assert "error" in stats

    def test_get_queue_stats_exception(self, monitoring_service, mock_celery_app):
        """Test queue stats exception handling."""
        monitoring_service.inspect.active = MagicMock(side_effect=Exception("Error"))

        stats = monitoring_service.get_queue_stats()

        assert "error" in stats
