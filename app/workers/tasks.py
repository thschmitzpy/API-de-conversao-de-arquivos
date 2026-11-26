from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timedelta, timezone

from celery.utils.log import get_task_logger
from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.broker.celery_app import celery_app
from app.config import get_settings
from app.database import SessionLocal
from app.metrics import JOB_PROCESSING_SECONDS, JOBS_FINISHED
from app.models import Job, JobStatus
from app.operations import Operation
from app.schemas import WebhookPayload
from app.storage.minio_client import (
    delete_object,
    download_bytes,
    presigned_get_url,
    upload_stream,
)
from app.webhook import notifier
from app.webhook.url_guard import UnsafeCallbackUrl, validate_callback_url
from app.workers.processors import (
    audio_extract,
    csv_validate,
    document_convert,
    excel_to_csv,
    image,
    ocr_extract,
    pdf_extract_text,
    pdf_merge,
    pdf_watermark,
    video_transcode,
)
from app.workers.processors.base import Processor
from app.workers.progress import ProgressCallback, reporting_progress

logger = get_task_logger(__name__)

_PROCESSORS: dict[str, Processor] = {
    Operation.IMAGE_THUMBNAIL: image.thumbnail,
    Operation.CSV_VALIDATE: csv_validate.validate,
    Operation.EXCEL_TO_CSV: excel_to_csv.to_csv,
    Operation.PDF_EXTRACT_TEXT: pdf_extract_text.extract_text,
    Operation.PDF_MERGE: pdf_merge.merge,
    Operation.PDF_WATERMARK: pdf_watermark.watermark,
    Operation.VIDEO_TRANSCODE: video_transcode.transcode,
    Operation.AUDIO_EXTRACT: audio_extract.extract,
    Operation.OCR_EXTRACT: ocr_extract.extract,
    Operation.DOCUMENT_CONVERT: document_convert.convert,
}


REAPED_ERROR_MESSAGE = "O processamento foi interrompido. Envie o arquivo novamente."

GENERIC_ERROR_MESSAGE = "Nao foi possivel processar o arquivo. Tente novamente mais tarde."

MAX_ERROR_MESSAGE_LENGTH = 300

_ABSOLUTE_PATH = re.compile(r"(?<![\w/])/[\w.-]+(?:/[\w.-]+)+")

PURGE_BATCH_SIZE = 200

PROGRESS_MIN_INTERVAL_SECONDS = 1.0


@celery_app.task(name="app.workers.tasks.process_job")
def process_job(job_id: str) -> None:
    settings = get_settings()
    job_uuid = uuid.UUID(job_id)

    with SessionLocal() as db:
        job = db.get(Job, job_uuid)
        if job is None:
            logger.error("Job nao encontrado no banco", extra={"job_id": job_id})
            return

        operation = job.operation
        processor = _PROCESSORS.get(operation)
        if processor is None:
            job.status = JobStatus.FAILED
            job.error_message = f"Operacao '{operation}' nao suportada"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            logger.error(
                "Operacao nao suportada",
                extra={"job_id": job_id, "operation": operation},
            )
            JOBS_FINISHED.labels(operation=operation, status="unsupported").inc()
        else:
            claimed = db.execute(
                update(Job)
                .where(Job.id == job_uuid, Job.status == JobStatus.PENDING)
                .values(
                    status=JobStatus.PROCESSING,
                    started_at=datetime.now(timezone.utc),
                )
            ).rowcount
            db.commit()
            if not claimed:
                logger.warning(
                    "Job ja encerrado, ignorando",
                    extra={"job_id": job_id, "operation": operation},
                )
                return

            started = time.monotonic()
            try:
                input_stream = download_bytes(
                    settings.minio_bucket_input,
                    job.input_key,
                )
                with reporting_progress(_progress_writer(db, job_uuid)):
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
                if job.progress is not None:
                    job.progress = 100
                job.status = JobStatus.DONE
                job.finished_at = datetime.now(timezone.utc)
                db.commit()
                logger.info(
                    "Job concluido",
                    extra={"job_id": job_id, "operation": operation},
                )
                JOBS_FINISHED.labels(operation=operation, status="done").inc()

            except Exception as exc:
                db.rollback()
                job = db.get(Job, job_uuid)
                if job is not None:
                    job.status = JobStatus.FAILED
                    job.error_message = _public_error_message(exc)
                    job.finished_at = datetime.now(timezone.utc)
                    db.commit()
                logger.exception(
                    "Job falhou",
                    extra={"job_id": job_id, "operation": operation},
                )
                JOBS_FINISHED.labels(operation=operation, status="failed").inc()
            finally:
                JOB_PROCESSING_SECONDS.labels(operation=operation).observe(
                    time.monotonic() - started
                )

        job = db.get(Job, job_uuid)
        if job is not None and job.callback_url:
            deliver_webhook.delay(job_id)


@celery_app.task(name="app.workers.tasks.reap_stuck_jobs")
def reap_stuck_jobs() -> int:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    pending_cutoff = now - timedelta(seconds=settings.job_pending_timeout_seconds)
    processing_cutoff = now - timedelta(seconds=settings.job_processing_timeout_seconds)

    with SessionLocal() as db:
        reaped = db.scalars(
            update(Job)
            .where(
                or_(
                    and_(Job.status == JobStatus.PENDING, Job.created_at < pending_cutoff),
                    and_(Job.status == JobStatus.PROCESSING, Job.started_at < processing_cutoff),
                )
            )
            .values(
                status=JobStatus.FAILED,
                error_message=REAPED_ERROR_MESSAGE,
                finished_at=now,
            )
            .returning(Job)
        ).all()
        db.commit()

        for job in reaped:
            logger.warning(
                "Job parado encerrado",
                extra={"job_id": str(job.id), "operation": job.operation},
            )
            JOBS_FINISHED.labels(operation=job.operation, status="reaped").inc()
            if job.callback_url:
                deliver_webhook.delay(str(job.id))

    return len(reaped)


@celery_app.task(name="app.workers.tasks.purge_expired_files")
def purge_expired_files() -> int:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=settings.file_retention_hours)

    with SessionLocal() as db:
        # finished_at so e preenchido em DONE e FAILED (inclusive pelo reaper).
        expired = db.scalars(
            select(Job)
            .where(Job.finished_at < cutoff, Job.files_purged_at.is_(None))
            .order_by(Job.finished_at)
            .limit(PURGE_BATCH_SIZE)
        ).all()

        purged = 0
        for job in expired:
            try:
                delete_object(settings.minio_bucket_input, job.input_key)
                if job.output_key:
                    delete_object(settings.minio_bucket_output, job.output_key)
            except Exception:

                logger.exception(
                    "Falha ao remover arquivos expirados",
                    extra={"job_id": str(job.id), "operation": job.operation},
                )
                break

            job.files_purged_at = now
            db.commit()
            purged += 1
            logger.info(
                "Arquivos expirados removidos",
                extra={"job_id": str(job.id), "operation": job.operation},
            )

    return purged


def _progress_writer(db: Session, job_uuid: uuid.UUID) -> ProgressCallback:
    last_percent = -1
    last_write = 0.0

    def write(fraction: float) -> None:
        nonlocal last_percent, last_write
        percent = int(fraction * 100)
        now = time.monotonic()
        if percent <= last_percent or now - last_write < PROGRESS_MIN_INTERVAL_SECONDS:
            return
        try:
            db.execute(
                update(Job)
                .where(Job.id == job_uuid, Job.status == JobStatus.PROCESSING)
                .values(progress=percent)
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.warning(
                "Falha ao gravar progresso",
                extra={"job_id": str(job_uuid)},
                exc_info=True,
            )
            return
        last_percent, last_write = percent, now

    return write


def _public_error_message(exc: Exception) -> str:
    # ValueError e o contrato dos processors para entrada ou parametro invalido.
    # Qualquer outra excecao (storage, banco, bug) vira mensagem generica;
    # o detalhe fica so no log.
    if not isinstance(exc, ValueError):
        return GENERIC_ERROR_MESSAGE
    message = _ABSOLUTE_PATH.sub("<arquivo>", str(exc)).strip()
    if not message:
        return GENERIC_ERROR_MESSAGE
    if len(message) > MAX_ERROR_MESSAGE_LENGTH:
        message = message[: MAX_ERROR_MESSAGE_LENGTH - 3] + "..."
    return message


@celery_app.task(
    bind=True,
    name="app.workers.tasks.deliver_webhook",
    ignore_result=True,
    max_retries=None,
)
def deliver_webhook(self, job_id: str) -> None:
    settings = get_settings()

    with SessionLocal() as db:
        job = db.get(Job, uuid.UUID(job_id))
        if job is None or not job.callback_url or job.callback_delivered_at:
            return

        try:
            validate_callback_url(
                job.callback_url,
                allow_private=settings.webhook_allow_private_targets,
            )
        except UnsafeCallbackUrl as exc:
            logger.warning(
                "Webhook bloqueado",
                extra={"job_id": job_id, "reason": str(exc)},
            )
            return

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

        job.callback_attempts += 1
        db.commit()
        attempts = job.callback_attempts

        try:
            notifier.send(job.callback_url, payload)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            if notifier.is_retryable(exc) and attempts < settings.webhook_max_retries:
                logger.warning(
                    "Webhook falhou, nova tentativa agendada",
                    extra={"job_id": job_id, "attempts": attempts, "error": error},
                )
                raise self.retry(exc=exc, countdown=min(2 ** (attempts - 1), 30))
            logger.warning(
                "Webhook falhou",
                extra={"job_id": job_id, "attempts": attempts, "error": error},
            )
            return

        job.callback_delivered_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(
            "Webhook entregue",
            extra={"job_id": job_id, "attempts": attempts},
        )
