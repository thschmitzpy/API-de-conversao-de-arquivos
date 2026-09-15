from __future__ import annotations

import uuid
from datetime import datetime, timezone

from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session

from app.broker.celery_app import celery_app
from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models import Job, JobStatus
from app.schemas import WebhookPayload
from app.storage.minio_client import (
    download_bytes,
    presigned_get_url,
    upload_stream,
)
from app.webhook import notifier
from app.workers.processors import csv_validate, image
from app.workers.processors.base import Processor

logger = get_task_logger(__name__)

_PROCESSORS: dict[str, Processor] = {
    "image.thumbnail": image.thumbnail,
    "csv.validate": csv_validate.validate,
}


@celery_app.task(name="app.workers.tasks.process_job")
def process_job(job_id: str) -> None:
    settings = get_settings()
    job_uuid = uuid.UUID(job_id)

    with SessionLocal() as db:
        job = db.get(Job, job_uuid)
        if job is None:
            logger.error("Job %s nao encontrado no banco", job_id)
            return

        processor = _PROCESSORS.get(job.operation)
        if processor is None:
            job.status = JobStatus.FAILED
            job.error_message = f"Operacao '{job.operation}' nao suportada"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            logger.error("Job %s: operacao %s nao suportada", job_id, job.operation)
        else:
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.now(timezone.utc)
            db.commit()

            try:
                input_stream = download_bytes(
                    settings.minio_bucket_input,
                    job.input_key,
                )
                result = processor(input_stream, job.parameters)

                output_key = f"{job.id}/output.{result.output_extension}"
                output_size = result.output.getbuffer().nbytes
                upload_stream(
                    bucket=settings.minio_bucket_output,
                    key=output_key,
                    stream=result.output,
                    size=output_size,
                    content_type=result.output_content_type,
                )

                job.output_key = output_key
                job.output_content_type = result.output_content_type
                job.result_metadata = result.result_metadata
                job.status = JobStatus.DONE
                job.finished_at = datetime.now(timezone.utc)
                db.commit()
                logger.info("Job %s concluido (%s)", job_id, job.operation)

            except Exception as exc:
                db.rollback()
                job = db.get(Job, job_uuid)
                if job is not None:
                    job.status = JobStatus.FAILED
                    job.error_message = f"{type(exc).__name__}: {exc}"
                    job.finished_at = datetime.now(timezone.utc)
                    db.commit()
                logger.exception("Job %s falhou", job_id)

        job = db.get(Job, job_uuid)
        if job is not None and job.callback_url:
            _deliver_webhook(db, job, settings)


def _deliver_webhook(db: Session, job: Job, settings: Settings) -> None:
    output_url: str | None = None
    if job.output_key:
        output_url = presigned_get_url(
            bucket=settings.minio_bucket_output,
            key=job.output_key,
        )

    event = "job.completed" if job.status == JobStatus.DONE else "job.failed"
    payload = WebhookPayload(
        event=event,
        job_id=job.id,
        status=job.status,
        operation=job.operation,
        output_url=output_url,
        result_metadata=job.result_metadata,
        error_message=job.error_message,
        finished_at=job.finished_at or datetime.now(timezone.utc),
    )

    delivery = notifier.deliver(job.callback_url, payload)

    job.callback_attempts = delivery.attempts
    if delivery.delivered:
        job.callback_delivered_at = datetime.now(timezone.utc)
    db.commit()

    if delivery.delivered:
        logger.info(
            "Webhook do job %s entregue em %d tentativa(s)",
            job.id,
            delivery.attempts,
        )
    else:
        logger.warning(
            "Webhook do job %s falhou apos %d tentativa(s): %s",
            job.id,
            delivery.attempts,
            delivery.error,
        )
