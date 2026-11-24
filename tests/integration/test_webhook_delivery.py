from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx
import pytest

from app.config import get_settings
from app.database import SessionLocal
from app.models import Job, JobStatus
from app.webhook.url_guard import UnsafeCallbackUrl
from app.workers import tasks

CALLBACK_URL = "https://cliente.example/webhook"


class _Receptor:
    def __init__(self):
        self.payloads = []
        self.falhas: list[Exception] = []

    def send(self, url, payload):
        self.payloads.append(payload)
        if self.falhas:
            raise self.falhas.pop(0)


@pytest.fixture(autouse=True)
def _callback_liberado(monkeypatch):
    monkeypatch.setattr(tasks, "validate_callback_url", lambda *a, **kw: None)


@pytest.fixture
def receptor(monkeypatch):
    receptor = _Receptor()
    monkeypatch.setattr(tasks.notifier, "send", receptor.send)
    return receptor


def _erro_http(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", CALLBACK_URL)
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(str(status), request=request, response=response)


def _create_job(**fields) -> str:
    job_id = uuid.uuid4()
    with SessionLocal() as db:
        db.add(
            Job(
                id=job_id,
                status=JobStatus.FAILED,
                operation="image.thumbnail",
                input_key=f"{job_id}/test.png",
                input_filename="test.png",
                input_content_type="image/png",
                input_size_bytes=1,
                parameters={},
                error_message="falhou",
                finished_at=datetime.now(timezone.utc),
                callback_url=CALLBACK_URL,
                **fields,
            )
        )
        db.commit()
    return str(job_id)


def _load_job(job_id: str) -> Job:
    with SessionLocal() as db:
        return db.get(Job, uuid.UUID(job_id))


def test_entrega_com_sucesso_marca_job(receptor):
    job_id = _create_job()

    tasks.deliver_webhook.apply(args=[job_id])

    assert len(receptor.payloads) == 1
    assert receptor.payloads[0].event == "job.failed"
    job = _load_job(job_id)
    assert job.callback_attempts == 1
    assert job.callback_delivered_at is not None


def test_5xx_retenta_ate_o_limite(receptor, monkeypatch):
    monkeypatch.setattr(get_settings(), "webhook_max_retries", 3)
    receptor.falhas = [_erro_http(500) for _ in range(5)]
    job_id = _create_job()

    tasks.deliver_webhook.apply(args=[job_id])

    assert len(receptor.payloads) == 3
    job = _load_job(job_id)
    assert job.callback_attempts == 3
    assert job.callback_delivered_at is None


def test_5xx_seguido_de_sucesso(receptor):
    receptor.falhas = [_erro_http(503)]
    job_id = _create_job()

    tasks.deliver_webhook.apply(args=[job_id])

    assert len(receptor.payloads) == 2
    job = _load_job(job_id)
    assert job.callback_attempts == 2
    assert job.callback_delivered_at is not None


def test_4xx_nao_retenta(receptor):
    receptor.falhas = [_erro_http(404)]
    job_id = _create_job()

    tasks.deliver_webhook.apply(args=[job_id])

    assert len(receptor.payloads) == 1
    job = _load_job(job_id)
    assert job.callback_attempts == 1
    assert job.callback_delivered_at is None


def test_job_ja_entregue_nao_reenvia(receptor):
    job_id = _create_job(callback_delivered_at=datetime.now(timezone.utc))

    tasks.deliver_webhook.apply(args=[job_id])

    assert receptor.payloads == []


def test_callback_bloqueado_nao_envia(receptor, monkeypatch):
    def _bloqueia(*_, **__):
        raise UnsafeCallbackUrl("callback_url aponta para endereco interno ou reservado")

    monkeypatch.setattr(tasks, "validate_callback_url", _bloqueia)
    job_id = _create_job()

    tasks.deliver_webhook.apply(args=[job_id])

    assert receptor.payloads == []
    assert _load_job(job_id).callback_attempts == 0
