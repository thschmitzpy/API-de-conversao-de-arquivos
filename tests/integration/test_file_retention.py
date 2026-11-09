import io
import uuid
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.database import SessionLocal
from app.models import Job, JobStatus
from app.storage.minio_client import upload_stream
from app.workers import tasks

from tests.integration.conftest import object_exists


def _put(bucket: str, key: str) -> None:
    upload_stream(bucket, key, io.BytesIO(b"data"), 4, "image/png")


def _create_job(status: JobStatus, age_hours: float) -> uuid.UUID:
    settings = get_settings()
    moment = datetime.now(timezone.utc) - timedelta(hours=age_hours)
    job_id = uuid.uuid4()
    input_key = f"{job_id}/test.png"
    output_key = f"{job_id}/output.png" if status == JobStatus.DONE else None

    _put(settings.minio_bucket_input, input_key)
    if output_key:
        _put(settings.minio_bucket_output, output_key)

    finished = status in (JobStatus.DONE, JobStatus.FAILED)
    with SessionLocal() as db:
        db.add(
            Job(
                id=job_id,
                status=status,
                operation="image.thumbnail",
                input_key=input_key,
                input_filename="test.png",
                input_content_type="image/png",
                input_size_bytes=4,
                output_key=output_key,
                output_content_type="image/png" if output_key else None,
                parameters={},
                created_at=moment,
                started_at=moment,
                finished_at=moment if finished else None,
            )
        )
        db.commit()
    return job_id


def _load_job(job_id: uuid.UUID) -> Job:
    with SessionLocal() as db:
        return db.get(Job, job_id)


def test_purge_remove_arquivos_de_job_expirado():
    job_id = _create_job(JobStatus.DONE, age_hours=48)

    assert tasks.purge_expired_files() == 1

    settings = get_settings()
    assert not object_exists(settings.minio_bucket_input, f"{job_id}/test.png")
    assert not object_exists(settings.minio_bucket_output, f"{job_id}/output.png")
    assert _load_job(job_id).files_purged_at is not None


def test_purge_inclui_job_que_falhou():
    job_id = _create_job(JobStatus.FAILED, age_hours=48)

    assert tasks.purge_expired_files() == 1

    assert not object_exists(get_settings().minio_bucket_input, f"{job_id}/test.png")


def test_purge_preserva_jobs_recentes_e_em_andamento():
    recente = _create_job(JobStatus.DONE, age_hours=1)
    em_andamento = _create_job(JobStatus.PROCESSING, age_hours=48)

    assert tasks.purge_expired_files() == 0

    settings = get_settings()
    assert object_exists(settings.minio_bucket_output, f"{recente}/output.png")
    assert object_exists(settings.minio_bucket_input, f"{em_andamento}/test.png")


def test_purge_nao_repete_job_ja_limpo():
    _create_job(JobStatus.DONE, age_hours=48)

    assert tasks.purge_expired_files() == 1
    assert tasks.purge_expired_files() == 0


def test_purge_com_storage_fora_tenta_de_novo_na_proxima_rodada(monkeypatch):
    job_id = _create_job(JobStatus.DONE, age_hours=48)

    def _storage_fora(*_):
        raise ConnectionError("minio fora do ar")

    monkeypatch.setattr(tasks, "delete_object", _storage_fora)
    assert tasks.purge_expired_files() == 0
    assert _load_job(job_id).files_purged_at is None

    monkeypatch.undo()
    assert tasks.purge_expired_files() == 1


def test_get_informa_expiracao_e_omite_link_apos_limpeza(client):
    retention = timedelta(hours=get_settings().file_retention_hours)
    recente = _create_job(JobStatus.DONE, age_hours=1)
    expirado = _create_job(JobStatus.DONE, age_hours=48)
    tasks.purge_expired_files()

    body = client.get(f"/jobs/{recente}").json()
    assert body["output_url"] is not None
    assert body["files_purged_at"] is None
    assert datetime.fromisoformat(body["expires_at"]) == (
            datetime.fromisoformat(body["finished_at"]) + retention
    )

    body = client.get(f"/jobs/{expirado}").json()
    assert body["output_url"] is None
    assert body["files_purged_at"] is not None


def test_download_de_job_expirado_retorna_410(client):
    job_id = _create_job(JobStatus.DONE, age_hours=48)
    tasks.purge_expired_files()

    response = client.get(f"/jobs/{job_id}/download")

    assert response.status_code == 410
    assert response.json() == {"detail": "Resultado expirado e removido do storage"}
