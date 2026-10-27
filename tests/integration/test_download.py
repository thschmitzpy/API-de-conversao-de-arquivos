from __future__ import annotations

import io
import uuid

from app.config import get_settings
from app.database import SessionLocal
from app.models import Job, JobStatus
from app.storage.minio_client import upload_stream


def _criar_job(
        status: JobStatus,
        input_filename: str = "foto.jpg",
        com_output: bool = False,
) -> uuid.UUID:
    job_id = uuid.uuid4()
    with SessionLocal() as db:
        db.add(
            Job(
                id=job_id,
                status=status,
                operation="image.thumbnail",
                input_key=f"{job_id}/{input_filename}",
                input_filename=input_filename,
                input_content_type="image/jpeg",
                input_size_bytes=10,
                parameters={},
                output_key=f"{job_id}/output.webp" if com_output else None,
                output_content_type="image/webp" if com_output else None,
            )
        )
        db.commit()
    return job_id


def _salvar_output(job_id: uuid.UUID, conteudo: bytes) -> None:
    upload_stream(
        bucket=get_settings().minio_bucket_output,
        key=f"{job_id}/output.webp",
        stream=io.BytesIO(conteudo),
        size=len(conteudo),
        content_type="image/webp",
    )


def test_download_transmite_o_resultado_com_nome_original(client):
    job_id = _criar_job(JobStatus.DONE, com_output=True)
    _salvar_output(job_id, b"conteudo-webp")

    r = client.get(f"/jobs/{job_id}/download")

    assert r.status_code == 200
    assert r.content == b"conteudo-webp"
    assert r.headers["content-type"] == "image/webp"
    assert r.headers["content-length"] == str(len(b"conteudo-webp"))
    assert 'filename="foto.webp"' in r.headers["content-disposition"]


def test_download_preserva_acentos_no_nome(client):
    job_id = _criar_job(JobStatus.DONE, input_filename="relatório final.jpg", com_output=True)
    _salvar_output(job_id, b"x")

    disposition = client.get(f"/jobs/{job_id}/download").headers["content-disposition"]

    assert "filename*=UTF-8''relat%C3%B3rio%20final.webp" in disposition
    assert 'filename="relatrio final.webp"' in disposition


def test_download_de_job_em_andamento_retorna_409(client):
    job_id = _criar_job(JobStatus.PROCESSING)

    r = client.get(f"/jobs/{job_id}/download")

    assert r.status_code == 409
    assert r.json()["detail"] == "Job sem resultado para download (status: PROCESSING)"


def test_download_de_job_falho_retorna_409(client):
    job_id = _criar_job(JobStatus.FAILED)

    assert client.get(f"/jobs/{job_id}/download").status_code == 409


def test_download_de_job_inexistente_retorna_404(client):
    assert client.get(f"/jobs/{uuid.uuid4()}/download").status_code == 404


def test_download_com_objeto_ausente_no_storage_retorna_502(client):
    job_id = _criar_job(JobStatus.DONE, com_output=True)

    r = client.get(f"/jobs/{job_id}/download")

    assert r.status_code == 502
    assert r.json()["detail"] == "Falha ao ler arquivo no storage"


def test_download_exige_api_key(client):
    job_id = _criar_job(JobStatus.DONE, com_output=True)

    r = client.get(f"/jobs/{job_id}/download", headers={"X-API-Key": ""})

    assert r.status_code in (401, 403)
