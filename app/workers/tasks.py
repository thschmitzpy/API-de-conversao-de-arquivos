from __future__ import annotations

import uuid
from datetime import datetime, timezone

from celery.utils.log import get_task_logger

from app.broker.celery_app import celery_app
from app.config import get_settings
from app.database import SessionLocal
from app.models import Job, JobStatus
from app.storage.minio_client import download_bytes, upload_stream
from app.workers.processors import image
from app.workers.processors.base import Processor

logger = get_task_logger(__name__)

_PROCESSORS: dict[str, Processor] = {
    "image.thumbnail": image.thumbnail,
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
            return

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
            logger.exception("Job %s falhou", job_id)                  # TODO: disparar webhook (proxima iteracao)


