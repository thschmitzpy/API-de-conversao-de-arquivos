from __future__ import annotations

import uuid
from io import BytesIO

import pytest

from app.database import SessionLocal
from app.models import Job, JobStatus
from app.operations import Operation
from app.workers import tasks
from app.workers.processors.base import ProcessorResult
from app.workers.progress import report_progress


class _Relogio:
    def __init__(self):
        self.agora = 1000.0

    def __call__(self):
        return self.agora


@pytest.fixture
def relogio(monkeypatch):
    relogio = _Relogio()
    monkeypatch.setattr(tasks.time, "monotonic", relogio)
    return relogio


@pytest.fixture
def storage_falso(monkeypatch):
    monkeypatch.setattr(tasks, "download_bytes", lambda *_: BytesIO(b"entrada"))
    monkeypatch.setattr(tasks, "upload_stream", lambda **_: None)


def _create_job(status: JobStatus = JobStatus.PROCESSING, **fields) -> uuid.UUID:
    job_id = uuid.uuid4()
    with SessionLocal() as db:
        db.add(
            Job(
                id=job_id,
                status=status,
                operation=Operation.VIDEO_TRANSCODE,
                input_key=f"{job_id}/video.mp4",
                input_filename="video.mp4",
                input_content_type="video/mp4",
                input_size_bytes=1,
                parameters={},
                **fields,
            )
        )
        db.commit()
    return job_id


def _progress(job_id: uuid.UUID) -> int | None:
    with SessionLocal() as db:
        return db.get(Job, job_id).progress


def _resultado() -> ProcessorResult:
    return ProcessorResult(
        output=BytesIO(b"saida"),
        output_content_type="video/mp4",
        output_extension="mp4",
    )


def test_get_job_sem_progresso_devolve_null(client):
    job_id = _create_job(JobStatus.PENDING)

    body = client.get(f"/jobs/{job_id}").json()

    assert "progress" in body
    assert body["progress"] is None


def test_get_job_devolve_progresso_gravado(client):
    job_id = _create_job(progress=42)

    assert client.get(f"/jobs/{job_id}").json()["progress"] == 42


def test_writer_grava_porcentagem(relogio):
    job_id = _create_job()

    with SessionLocal() as db:
        tasks._progress_writer(db, job_id)(0.375)

    assert _progress(job_id) == 37


def test_writer_respeita_intervalo_minimo(relogio):
    job_id = _create_job()

    with SessionLocal() as db:
        write = tasks._progress_writer(db, job_id)
        write(0.10)
        relogio.agora += 0.5
        write(0.20)
        assert _progress(job_id) == 10

        relogio.agora += tasks.PROGRESS_MIN_INTERVAL_SECONDS
        write(0.30)

    assert _progress(job_id) == 30


def test_writer_ignora_porcentagem_que_nao_avanca(relogio):
    job_id = _create_job()

    with SessionLocal() as db:
        write = tasks._progress_writer(db, job_id)
        write(0.50)
        relogio.agora += 5
        write(0.50)
        write(0.40)

    assert _progress(job_id) == 50


def test_writer_nao_grava_em_job_encerrado(relogio):
    job_id = _create_job(JobStatus.FAILED, error_message=tasks.REAPED_ERROR_MESSAGE)

    with SessionLocal() as db:
        tasks._progress_writer(db, job_id)(0.5)

    assert _progress(job_id) is None


def test_process_job_com_progresso_termina_em_100(storage_falso, monkeypatch):
    vistos: list[int | None] = []

    def processor(_stream, _parameters):
        report_progress(0.6)
        vistos.append(_progress(job_id))
        return _resultado()

    monkeypatch.setitem(tasks._PROCESSORS, Operation.VIDEO_TRANSCODE, processor)
    job_id = _create_job(JobStatus.PENDING)

    tasks.process_job(str(job_id))

    assert vistos == [60]
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        assert job.status == JobStatus.DONE
        assert job.progress == 100


def test_process_job_sem_progresso_mantem_null(storage_falso, monkeypatch):
    monkeypatch.setitem(
        tasks._PROCESSORS, Operation.VIDEO_TRANSCODE, lambda *_: _resultado()
    )
    job_id = _create_job(JobStatus.PENDING)

    tasks.process_job(str(job_id))

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        assert job.status == JobStatus.DONE
        assert job.progress is None
