from __future__ import annotations

from prometheus_client import Counter, Histogram

JOBS_CREATED = Counter(
    "jobs_created_total",
    "Total de jobs criados via POST /jobs",
    labelnames=["operation"],
)

JOBS_FINISHED = Counter(
    "jobs_finished_total",
    "Total de jobs finalizados pelo worker (done, failed ou unsupported)",
    labelnames=["operation", "status"],
)

JOB_PROCESSING_SECONDS = Histogram(
    "job_processing_seconds",
    "Duracao do processamento do job no worker (segundos)",
    labelnames=["operation"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),

)
