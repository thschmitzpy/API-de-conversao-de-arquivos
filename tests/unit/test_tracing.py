from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from opentelemetry.sdk.resources import SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider

from app import tracing


@pytest.fixture
def chamadas(monkeypatch):
    registro = {"providers": [], "instrumentados": [], "apps": []}

    class FakeInstrumentor:
        def __init__(self, nome):
            self.nome = nome

        def __call__(self):
            return self

        def instrument(self, **kwargs):
            registro["instrumentados"].append((self.nome, kwargs))

    monkeypatch.setattr(tracing.trace, "set_tracer_provider", registro["providers"].append)
    monkeypatch.setattr(tracing, "CeleryInstrumentor", FakeInstrumentor("celery"))
    monkeypatch.setattr(tracing, "SQLAlchemyInstrumentor", FakeInstrumentor("sqlalchemy"))
    monkeypatch.setattr(tracing, "HTTPXClientInstrumentor", FakeInstrumentor("httpx"))
    monkeypatch.setattr(
        tracing.FastAPIInstrumentor,
        "instrument_app",
        lambda app, **kwargs: registro["apps"].append((app, kwargs)),
    )
    yield registro
    for provider in registro["providers"]:
        provider.shutdown()


def _com_endpoint(monkeypatch, endpoint):
    monkeypatch.setattr(
        tracing, "get_settings", lambda: SimpleNamespace(otel_exporter_otlp_endpoint=endpoint)
    )


@pytest.mark.parametrize("endpoint", [None, ""])
def test_sem_endpoint_nao_liga(monkeypatch, chamadas, endpoint):
    _com_endpoint(monkeypatch, endpoint)

    assert tracing.configure_tracing("conversor-teste", app=FastAPI()) is False
    assert chamadas == {"providers": [], "instrumentados": [], "apps": []}


def test_com_endpoint_liga_provider_e_instrumentacoes(monkeypatch, chamadas):
    _com_endpoint(monkeypatch, "http://jaeger:4318")

    assert tracing.configure_tracing("conversor-teste") is True
    [provider] = chamadas["providers"]
    assert provider.resource.attributes[SERVICE_NAME] == "conversor-teste"
    assert chamadas["instrumentados"] == [
        ("celery", {}),
        ("sqlalchemy", {"engine": tracing.engine, "skip_dep_check": True}),
        ("httpx", {}),
    ]
    assert chamadas["apps"] == []


def test_com_app_instrumenta_fastapi_sem_probes(monkeypatch, chamadas):
    _com_endpoint(monkeypatch, "http://jaeger:4318")
    app = FastAPI()

    tracing.configure_tracing("conversor-teste", app=app)

    assert chamadas["apps"] == [
        (app, {"excluded_urls": tracing.EXCLUDED_URLS, "exclude_spans": ["receive", "send"]})
    ]


@pytest.mark.parametrize("endpoint", ["http://jaeger:4318", "http://jaeger:4318/"])
def test_traces_url(endpoint):
    assert tracing.traces_url(endpoint) == "http://jaeger:4318/v1/traces"


def test_tag_job_marca_span_atual():
    tracer = TracerProvider().get_tracer("teste")

    with tracer.start_as_current_span("requisicao") as span:
        tracing.tag_job("abc-123", "image.thumbnail")

    assert span.attributes["conversor.job_id"] == "abc-123"
    assert span.attributes["conversor.operation"] == "image.thumbnail"


def test_tag_job_sem_span_ativo_nao_falha():
    tracing.tag_job("abc-123")
