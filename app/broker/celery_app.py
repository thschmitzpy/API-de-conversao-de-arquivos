from celery import Celery
from celery.signals import worker_ready
from prometheus_client import start_http_server

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "conversor",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=540,
    worker_prefetch_multiplier=1,
)


@worker_ready.connect
def _start_metrics_server(**_: object) -> None:
    start_http_server(settings.metrics_port)
