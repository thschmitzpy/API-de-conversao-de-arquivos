from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.rate_limit import limiter


@pytest.fixture
def client() -> TestClient:
    limiter.reset()
    return TestClient(app, headers={"X-API-Key": "dev-key-local"})


def _upload_kwargs() -> dict:
    return {
        "files": {"file": ("a.txt", io.BytesIO(b"conteudo"), "text/plain")},
        "data": {"operation": "csv.validate"},
    }


def test_health_nao_tem_limite(client: TestClient) -> None:
    for _ in range(200):
        assert client.get("/health").status_code == 200


def test_get_job_respeita_limite(client: TestClient) -> None:
    settings = get_settings()
    limite = int(settings.rate_limit_get_job.split("/")[0])
    fake_id = "00000000-0000-0000-0000-000000000000"

    for _ in range(limite):
        resp = client.get(f"/jobs/{fake_id}")
        assert resp.status_code in (200, 404)

    resp = client.get(f"/jobs/{fake_id}")
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers or "retry-after" in resp.headers


def test_create_job_respeita_limite(client: TestClient) -> None:
    settings = get_settings()
    limite = int(settings.rate_limit_create_job.split("/")[0])

    for _ in range(limite):
        resp = client.post("/jobs", **_upload_kwargs())
        assert resp.status_code in (202, 400, 502, 500)

    resp = client.post("/jobs", **_upload_kwargs())
    assert resp.status_code == 429


def test_headers_de_rate_limit_presentes(client: TestClient) -> None:
    resp = client.post("/jobs", **_upload_kwargs())
    assert resp.status_code == 202
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers
