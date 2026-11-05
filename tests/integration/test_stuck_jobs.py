from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.database import SessionLocal
from app.models import Job, JobStatus
from app.workers import tasks

from tests.integration.conftest import make_png_bytes, object_exists


def _create_job(status: JobStatus, age_seconds: int = 0, **fields) -> uuid.UUID:
    moment = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    job_id = uuid.uuid4()
    with SessionLocal() as db:
        db.add(
            Job(
                id=job_id,
                status=status,
                operation="image.thumbnail",
                input_key=f"{job_id}/test.png",
                input_filename="test.png",
                input_content_type="image/png",
                input_size_bytes=1,
                parameters={},
                created_at=moment,
                started_at=moment if status == JobStatus.PROCESSING else None,
                **fields,
            )
        )
        db.commit()
    return job_id


def _load_job(job_id: uuid.UUID) -> Job:
    with SessionLocal() as db:
        return db.get(Job, job_id)


def test_reaper_encerra_job_preso_em_processing():
    job_id = _create_job(JobStatus.PROCESSING, age_seconds=3600)

    assert tasks.reap_stuck_jobs() == 1

    job = _load_job(job_id)
    assert job.status == JobStatus.FAILED
    assert job.error_message == tasks.REAPED_ERROR_MESSAGE
    assert job.finished_at is not None


def test_reaper_encerra_job_preso_em_pending():
    job_id = _create_job(JobStatus.PENDING, age_seconds=3600)

    assert tasks.reap_stuck_jobs() == 1

    assert _load_job(job_id).status == JobStatus.FAILED


def test_reaper_preserva_jobs_recentes_e_finalizados():
    pending = _create_job(JobStatus.PENDING, age_seconds=60)
    processing = _create_job(JobStatus.PROCESSING, age_seconds=60)
    done = _create_job(JobStatus.DONE, age_seconds=3600)

    assert tasks.reap_stuck_jobs() == 0

    assert _load_job(pending).status == JobStatus.PENDING
    assert _load_job(processing).status == JobStatus.PROCESSING
    assert _load_job(done).status == JobStatus.DONE


def test_reaper_notifica_webhook_do_job_encerrado(monkeypatch):
    delivered = []
    monkeypatch.setattr(
        tasks,
        "_deliver_webhook",
        lambda db, job, settings: delivered.append((job.id, job.status)),
    )
    job_id = _create_job(
        JobStatus.PROCESSING,
        age_seconds=3600,
        callback_url="http://cliente.example/webhook",
    )
    _create_job(JobStatus.PROCESSING, age_seconds=3600)

    assert tasks.reap_stuck_jobs() == 2

    assert delivered == [(job_id, JobStatus.FAILED)]


def test_process_job_ignora_job_ja_encerrado_pelo_reaper(monkeypatch):
    def _nao_deveria_rodar(*_):
        raise AssertionError("job encerrado nao pode ser processado")

    monkeypatch.setattr(tasks, "download_bytes", _nao_deveria_rodar)
    job_id = _create_job(JobStatus.FAILED, error_message=tasks.REAPED_ERROR_MESSAGE)

    tasks.process_job(str(job_id))

    job = _load_job(job_id)
    assert job.status == JobStatus.FAILED
    assert job.started_at is None


def test_post_jobs_fila_indisponivel_retorna_503_sem_deixar_orfaos(client, monkeypatch):
    fixed_id = uuid.uuid4()
    monkeypatch.setattr("app.api.jobs.uuid.uuid4", lambda: fixed_id)

    def _broker_fora(*_, **__):
        raise ConnectionError("redis fora do ar")

    monkeypatch.setattr("app.api.jobs.celery_app.send_task", _broker_fora)

    response = client.post(
        "/jobs",
        files={"file": ("test.png", make_png_bytes(), "image/png")},
        data={"operation": "image.thumbnail"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Fila de processamento indisponivel"}
    assert _load_job(fixed_id) is None
    settings = get_settings()
    assert not object_exists(settings.minio_bucket_input, f"{fixed_id}/test.png")
