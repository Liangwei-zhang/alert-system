"""
Celery application configuration.
"""
from celery import Celery

from infra.config import settings

celery_app = Celery(
    "stock-py",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.stock_tasks",
        "app.tasks.notification_tasks",
        "app.tasks.worker_tasks",
        "app.tasks.email_tasks",
        "app.tasks.message_tasks",
        "app.tasks.scanner_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
)