import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.forwarded_prefix import ForwardedPrefixMiddleware


@pytest.fixture
def client():
    app = FastAPI()
    app.add_middleware(ForwardedPrefixMiddleware)

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str, request: Request):
        return {"url": str(request.url_for("get_job", job_id=job_id))}

    return TestClient(app)


def test_sem_header_mantem_url_original(client):
    assert client.get("/jobs/abc").json()["url"] == "http://testserver/jobs/abc"


def test_prefixo_valido_entra_na_url(client):
    response = client.get("/jobs/abc", headers={"X-Forwarded-Prefix": "/api"})
    assert response.json()["url"] == "http://testserver/api/jobs/abc"


def test_prefixo_com_varios_segmentos(client):
    response = client.get("/jobs/abc", headers={"X-Forwarded-Prefix": "/v1/api"})
    assert response.json()["url"] == "http://testserver/v1/api/jobs/abc"


@pytest.mark.parametrize("prefixo", ["/api/", "//evil.com", "api", "/api?x=1", "/a b", ""])
def test_prefixo_invalido_e_ignorado(client, prefixo):
    response = client.get("/jobs/abc", headers={"X-Forwarded-Prefix": prefixo})
    assert response.json()["url"] == "http://testserver/jobs/abc"
