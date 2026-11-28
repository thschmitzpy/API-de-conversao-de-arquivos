from __future__ import annotations

import io
import uuid

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from app.config import get_settings
from app.database import SessionLocal
from app.models import Job, JobStatus
from app.operations import Operation
from app.storage import minio_client
from app.workers import tasks
from tests.integration.conftest import make_png_bytes


@pytest.fixture
def exporter(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("teste")
    monkeypatch.setattr(tasks, "tracer", tracer)
    monkeypatch.setattr(minio_client, "tracer", tracer)
    yield exporter, tracer
    provider.shutdown()


def _create_job() -> uuid.UUID:
    settings = get_settings()
    job_id = uuid.uuid4()
    png = make_png_bytes()
    minio_client.get_client().put_object(
        settings.minio_bucket_input, f"{job_id}/foto.png", io.BytesIO(png), len(png)
    )
    with SessionLocal() as db:
        db.add(
            Job(
                id=job_id,
                status=JobStatus.PENDING,
                operation=Operation.IMAGE_THUMBNAIL,
                input_key=f"{job_id}/foto.png",
                input_filename="foto.png",
                input_content_type="image/png",
                input_size_bytes=len(png),
                parameters={"width": 50, "height": 50},
            )
        )
        db.commit()
    return job_id


def _run(tracer, job_id: uuid.UUID):
    with tracer.start_as_current_span("run/process_job") as raiz:
        tasks.process_job(str(job_id))
    return raiz


def _status(job_id: uuid.UUID) -> JobStatus:
    with SessionLocal() as db:
        return db.get(Job, job_id).status


def test_job_concluido_gera_spans_de_storage_e_processor(exporter):
    spans_exportados, tracer = exporter
    job_id = _create_job()

    raiz = _run(tracer, job_id)

    assert _status(job_id) == JobStatus.DONE
    filhos = {
        span.name: span
        for span in spans_exportados.get_finished_spans()
        if span.parent is not None and span.parent.span_id == raiz.context.span_id
    }
    assert list(filhos) == ["storage.download", "processor image.thumbnail", "storage.upload"]
    settings = get_settings()
    assert filhos["storage.download"].attributes["storage.bucket"] == settings.minio_bucket_input
    assert filhos["storage.download"].attributes["storage.size_bytes"] > 0
    assert filhos["storage.upload"].attributes["storage.bucket"] == settings.minio_bucket_output
    assert filhos["storage.upload"].attributes["storage.size_bytes"] > 0


def test_task_marca_job_id_e_operation_no_span_da_task(exporter):
    _, tracer = exporter
    job_id = _create_job()

    raiz = _run(tracer, job_id)

    assert raiz.attributes["conversor.job_id"] == str(job_id)
    assert raiz.attributes["conversor.operation"] == "image.thumbnail"


def test_processor_que_falha_deixa_span_com_erro(exporter, monkeypatch):
    spans_exportados, tracer = exporter

    def _quebra(_stream, _parameters):
        raise ValueError("imagem corrompida")

    monkeypatch.setitem(tasks._PROCESSORS, Operation.IMAGE_THUMBNAIL, _quebra)
    job_id = _create_job()

    _run(tracer, job_id)

    assert _status(job_id) == JobStatus.FAILED
    [processor] = [
        span for span in spans_exportados.get_finished_spans()
        if span.name == "processor image.thumbnail"
    ]
    assert processor.status.status_code == StatusCode.ERROR
    assert processor.events[0].name == "exception"
    assert "imagem corrompida" in processor.events[0].attributes["exception.message"]
    assert not [
        span for span in spans_exportados.get_finished_spans() if span.name == "storage.upload"
    ]
