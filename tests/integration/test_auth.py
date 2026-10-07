from __future__ import annotations

import io

from fastapi.testclient import TestClient

from app.main import app


def _upload_kwargs() -> dict:
    return {
        "files": {"file": ("a.txt", io.BytesIO(b"conteudo"), "text/plain")},
        "data": {"operation": "csv.validate"},
    }


def test_post_jobs_sem_header_retorna_401() -> None:
    r = TestClient(app).post("/jobs", **_upload_kwargs())
    assert r.status_code == 401


def test_get_jobs_sem_header_retorna_401() -> None:
    r = TestClient(app).get("/jobs")
    assert r.status_code == 401


def test_get_job_por_id_sem_header_retorna_401() -> None:
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = TestClient(app).get(f"/jobs/{fake_id}")
    assert r.status_code == 401


def test_post_jobs_com_chave_invalida_retorna_403() -> None:
    headers = {"X-API-Key": "chave-que-nao-existe"}
    r = TestClient(app, headers=headers).post("/jobs", **_upload_kwargs())
    assert r.status_code == 403


def test_health_nao_exige_header() -> None:
    assert TestClient(app).get("/health").status_code == 200


def test_ready_nao_exige_header() -> None:
    assert TestClient(app).get("/ready").status_code in (200, 503)


def test_metrics_nao_exige_header() -> None:
    assert TestClient(app).get("/metrics").status_code == 200


def test_post_jobs_com_chave_valida_passa_do_auth(client: TestClient) -> None:
    r = client.post(
        "/jobs",
        files={"file": ("a.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")},
        data={"operation": "csv.validate"},
    )
    assert r.status_code not in (401, 403)
