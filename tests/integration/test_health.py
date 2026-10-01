from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_health_sempre_retorna_ok(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ready_com_tudo_de_pe_retorna_200(client: TestClient) -> None:
    r = client.get("/ready")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["checks"] == {"postgres": "ok", "redis": "ok", "minio": "ok"}


def test_ready_com_postgres_caido_retorna_503(client: TestClient) -> None:
    with patch("app.api.health._check_postgres", return_value="error: OperationalError"):
        r = client.get("/ready")
    assert r.status_code == 503
    data = r.json()
    assert data["status"] == "unavailable"
    assert data["checks"]["postgres"].startswith("error:")
    assert data["checks"]["redis"] == "ok"
    assert data["checks"]["minio"] == "ok"


def test_ready_com_redis_caido_retorna_503(client: TestClient) -> None:
    with patch("app.api.health._check_redis", return_value="error: ConnectionError"):
        r = client.get("/ready")
    assert r.status_code == 503
    assert r.json()["checks"]["redis"].startswith("error:")


def test_ready_com_minio_caido_retorna_503(client: TestClient) -> None:
    with patch("app.api.health._check_minio", return_value="error: S3Error"):
        r = client.get("/ready")
    assert r.status_code == 503
    assert r.json()["checks"]["minio"].startswith("error:")


def test_ready_com_todos_caidos_retorna_503_com_cada_erro(
        client: TestClient,
) -> None:
    with (
        patch("app.api.health._check_postgres", return_value="error: X"),
        patch("app.api.health._check_redis", return_value="error: Y"),
        patch("app.api.health._check_minio", return_value="error: Z"),
    ):
        r = client.get("/ready")
    assert r.status_code == 503
    data = r.json()
    assert data["status"] == "unavailable"
    assert all(v.startswith("error:") for v in data["checks"].values())
