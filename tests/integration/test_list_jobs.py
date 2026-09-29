from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import SessionLocal
from app.models import Job, JobStatus


def _insert_job(
        *,
        status: JobStatus = JobStatus.PENDING,
        operation: str = "image.thumbnail",
        created_at: datetime | None = None,
        error_message: str | None = None,
) -> uuid.UUID:
    job_id = uuid.uuid4()
    with SessionLocal() as db:
        db.add(
            Job(
                id=job_id,
                status=status,
                operation=operation,
                input_key=f"{job_id}/f.bin",
                input_filename="f.bin",
                input_content_type="application/octet-stream",
                input_size_bytes=10,
                parameters={},
                error_message=error_message,
            )
        )
        db.commit()
        if created_at is not None:
            db.execute(
                text("UPDATE jobs SET created_at = :ts WHERE id = :id"),
                {"ts": created_at, "id": job_id},
            )
            db.commit()
    return job_id


def test_list_jobs_sem_filtros_retorna_paginacao_default(client: TestClient) -> None:
    for _ in range(3):
        _insert_job()

    resp = client.get("/jobs")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert len(body["items"]) == 3


def test_list_jobs_filtra_por_status_unico(client: TestClient) -> None:
    _insert_job(status=JobStatus.DONE)
    _insert_job(status=JobStatus.DONE)
    _insert_job(status=JobStatus.FAILED)

    resp = client.get("/jobs", params={"status": "DONE"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert all(item["status"] == "DONE" for item in body["items"])


def test_list_jobs_filtra_por_multiplos_status(client: TestClient) -> None:
    _insert_job(status=JobStatus.DONE)
    _insert_job(status=JobStatus.FAILED)
    _insert_job(status=JobStatus.PENDING)

    resp = client.get("/jobs", params=[("status", "DONE"), ("status", "FAILED")])

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert {item["status"] for item in body["items"]} == {"DONE", "FAILED"}


def test_list_jobs_filtra_por_operation(client: TestClient) -> None:
    _insert_job(operation="image.thumbnail")
    _insert_job(operation="image.thumbnail")
    _insert_job(operation="csv.validate")

    resp = client.get("/jobs", params={"operation": "csv.validate"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["operation"] == "csv.validate"


def test_list_jobs_paginacao(client: TestClient) -> None:
    for _ in range(5):
        _insert_job()

    resp = client.get("/jobs", params={"limit": 2, "offset": 2})
    resp = client.get("/jobs", params={"limit": 2, "offset": 2})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert body["limit"] == 2
    assert body["offset"] == 2
    assert len(body["items"]) == 2


def test_list_jobs_order_asc(client: TestClient) -> None:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ids = [
        _insert_job(created_at=base.replace(day=1)),
        _insert_job(created_at=base.replace(day=2)),
        _insert_job(created_at=base.replace(day=3)),
    ]

    resp = client.get("/jobs", params={"order": "created_at:asc"})

    assert resp.status_code == 200
    returned = [item["id"] for item in resp.json()["items"]]
    assert returned == [str(i) for i in ids]


def test_list_jobs_order_invalido_retorna_400(client: TestClient) -> None:
    resp = client.get("/jobs", params={"order": "banana"})
    assert resp.status_code == 400


def test_list_jobs_limit_fora_do_range_retorna_422(client: TestClient) -> None:
    assert client.get("/jobs", params={"limit": 0}).status_code == 422
    assert client.get("/jobs", params={"limit": 101}).status_code == 422


def test_list_jobs_lista_vazia(client: TestClient) -> None:
    resp = client.get("/jobs")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []
