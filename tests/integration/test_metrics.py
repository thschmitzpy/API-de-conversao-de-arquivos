from __future__ import annotations

from fastapi.testclient import TestClient

from tests.integration.conftest import make_png_bytes


def test_endpoint_metrics_responde_formato_prometheus(client: TestClient) -> None:
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    body = r.text
    assert "# HELP" in body
    assert "# TYPE" in body


def test_criar_job_incrementa_jobs_created_total(client: TestClient) -> None:
    png = make_png_bytes()
    r = client.post(
        "/jobs",
        files={"file": ("teste.png", png, "image/png")},
        data={
            "operation": "image.thumbnail",
            "parameters": '{"width": 50, "height": 50}',
        },
    )
    assert r.status_code == 202

    body = client.get("/metrics").text
    assert 'jobs_created_total{operation="image.thumbnail"}' in body


def test_requisicao_http_aparece_nas_metricas_do_instrumentator(
        client: TestClient,
) -> None:
    client.get("/jobs?limit=1")
    body = client.get("/metrics").text
    assert "http_request" in body
