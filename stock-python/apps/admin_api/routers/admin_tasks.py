"""
Admin API endpoints for Celery task monitoring and management.
"""
from typing import List, Optional
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, status
from celery import Celery

from domains.system.monitoring_service import MonitoringService, monitoring_service
from apps.workers.celery_app import celery_app


router = APIRouter(prefix="/admin/tasks", tags=["admin", "tasks"])


# ============== Pydantic Schemas ==============

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    state: str
    ready: bool
    successful: bool
    traceback: Optional[str] = None
    result: Optional[str] = None
    runtime_seconds: Optional[float] = None
    eta: Optional[str] = None
    expires: Optional[str] = None


class WorkerStatusResponse(BaseModel):
    name: str
    status: str
    pool: dict = {}
    consumer: dict = {}
    prefetch_multiplier: Optional[int] = None
    max_tasks_per_child: Optional[int] = None


class TaskSummaryResponse(BaseModel):
    running: int
    scheduled: int
    reserved: int
    total_active: int


class SystemHealthResponse(BaseModel):
    status: str
    celery: str
    workers: str
    queue: str
    timestamp: str
    details: dict = {}


class DashboardResponse(BaseModel):
    health: dict
    workers: dict
    queues: dict
    stats: dict


def get_monitoring_service() -> MonitoringService:
    """Get monitoring service instance."""
    return MonitoringService(celery_app)


# ============== Task Status Endpoints ==============

@router.get("/status/{task_id}", response_model=TaskStatusResponse)
def get_task_status(
    task_id: str,
    service: MonitoringService = Depends(get_monitoring_service),
):
    """Get status of a specific Celery task."""
    result = service.get_task_status(task_id)
    
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["error"],
        )
    
    return TaskStatusResponse(**result)


@router.get("/result/{task_id}")
def get_task_result(
    task_id: str,
    service: MonitoringService = Depends(get_monitoring_service),
):
    """Get result of a completed task."""
    result = service.get_task_result(task_id)
    
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found or not completed",
        )
    
    return {"task_id": task_id, "result": result}


@router.get("/stats")
def get_task_stats(
    service: MonitoringService = Depends(get_monitoring_service),
):
    """Get overall task statistics."""
    return service.get_task_stats_from_backend()


# ============== Queue Status Endpoints ==============

@router.get("/queues")
def get_queue_status(
    service: MonitoringService = Depends(get_monitoring_service),
):
    """Get queue status with all active tasks."""
    return service.get_queue_stats()


@router.get("/queues/pending", response_model=List[dict])
def get_pending_tasks(
    limit: int = 100,
    service: MonitoringService = Depends(get_monitoring_service),
):
    """Get pending tasks in the queue."""
    return service.get_pending_tasks(limit=limit)


@router.get("/queues/running", response_model=List[dict])
def get_running_tasks(
    service: MonitoringService = Depends(get_monitoring_service),
):
    """Get currently running tasks."""
    return service.get_running_tasks()


# ============== Worker Status Endpoints ==============

@router.get("/workers")
def get_worker_status(
    service: MonitoringService = Depends(get_monitoring_service),
):
    """Get worker status (ping)."""
    return service.get_worker_status()


@router.get("/workers/stats")
def get_worker_stats(
    service: MonitoringService = Depends(get_monitoring_service),
):
    """Get detailed worker statistics."""
    return service.get_worker_stats()


@router.get("/workers/active", response_model=List[str])
def get_active_workers(
    service: MonitoringService = Depends(get_monitoring_service),
):
    """Get list of active worker names."""
    return service.get_active_workers()


# ============== System Health Endpoints ==============

@router.get("/health", response_model=SystemHealthResponse)
def get_system_health(
    service: MonitoringService = Depends(get_monitoring_service),
):
    """Get overall system health status."""
    return SystemHealthResponse(**service.get_system_health())


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    service: MonitoringService = Depends(get_monitoring_service),
):
    """Get combined dashboard data."""
    return DashboardResponse(**service.get_dashboard_data())
