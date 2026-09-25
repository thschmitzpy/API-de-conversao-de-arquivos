from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone

import httpx
import pytest

from app.models import JobStatus
from app.schemas import WebhookPayload
from app.webhook import notifier


class _FakeSettings:
    def __init__(
            self,
            secret: str = "test-secret",
            max_retries: int = 3,
            timeout: int = 5,
    ):
        self.webhook_signing_secret = secret
        self.webhook_max_retries = max_retries
        self.webhook_timeout_seconds = timeout


class _HttpxRecorder:
    def __init__(self):
        self.calls: list[dict] = []
        self._queue: list = []

    def queue(self, *items):
        self._queue = list(items)

    def _pop(self):
        if not self._queue:
            raise AssertionError("mock httpx: fila de respostas esgotada")
        return self._queue.pop(0)


def _install_fake_client(monkeypatch, recorder: _HttpxRecorder):
    class _FakeClient:
        def __init__(self, timeout=None):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def post(self, url, content, headers):
            recorder.calls.append(
                {"url": url, "content": content, "headers": dict(headers)}
            )
            item = recorder._pop()
            if isinstance(item, BaseException):
                raise item
            return item

    monkeypatch.setattr(notifier.httpx, "Client", _FakeClient)


@pytest.fixture
def fake_settings(monkeypatch):
    settings = _FakeSettings()
    monkeypatch.setattr(notifier, "get_settings", lambda: settings)
    return settings


@pytest.fixture
def http(monkeypatch):
    recorder = _HttpxRecorder()
    _install_fake_client(monkeypatch, recorder)
    return recorder


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _: None)


def _payload(event: str = "job.completed") -> WebhookPayload:
    return WebhookPayload(
        event=event,
        job_id=uuid.uuid4(),
        status=JobStatus.DONE if event == "job.completed" else JobStatus.FAILED,
        operation="image.thumbnail",
        output_url="https://example.com/out.png",
        result_metadata={"width": 100},
        finished_at=datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc),
    )


def _ok(url: str = "https://cb.example.com/hook") -> httpx.Response:
    return httpx.Response(status_code=200, request=httpx.Request("POST", url))


def _resp(status: int, url: str = "https://cb.example.com/hook") -> httpx.Response:
    return httpx.Response(status_code=status, request=httpx.Request("POST", url))


def test_delivery_sucesso_com_200(fake_settings, http):
    http.queue(_ok())

    result = notifier.deliver("https://cb.example.com/hook", _payload())

    assert result.delivered is True
    assert result.attempts == 1
    assert result.error is None


def test_body_enviado_e_json_do_payload(fake_settings, http):
    http.queue(_ok())
    payload = _payload()

    notifier.deliver("https://cb.example.com/hook", payload)

    sent = json.loads(http.calls[0]["content"].decode("utf-8"))
    assert sent["event"] == "job.completed"
    assert sent["operation"] == "image.thumbnail"


def test_assinatura_hmac_correta_no_header(fake_settings, http):
    http.queue(_ok())
    payload = _payload()

    notifier.deliver("https://cb.example.com/hook", payload)

    body = http.calls[0]["content"]
    expected = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    assert http.calls[0]["headers"]["X-Conversor-Signature"] == f"sha256={expected}"


def test_header_evento_reflete_payload_event(fake_settings, http):
    http.queue(_ok())

    notifier.deliver("https://cb.example.com/hook", _payload(event="job.failed"))

    assert http.calls[0]["headers"]["X-Conversor-Event"] == "job.failed"


def test_content_type_application_json(fake_settings, http):
    http.queue(_ok())

    notifier.deliver("https://cb.example.com/hook", _payload())

    assert http.calls[0]["headers"]["Content-Type"] == "application/json"


def test_user_agent_customizado(fake_settings, http):
    http.queue(_ok())

    notifier.deliver("https://cb.example.com/hook", _payload())

    assert "ConversorArquivos-Webhook" in http.calls[0]["headers"]["User-Agent"]


def test_500_retenta_ate_max_retries_e_falha(fake_settings, http):
    http.queue(_resp(500), _resp(500), _resp(500))

    result = notifier.deliver("https://cb.example.com/hook", _payload())

    assert result.delivered is False
    assert result.attempts == 3
    assert "500" in result.error


def test_500_seguido_de_200_sucesso_em_2_tentativas(fake_settings, http):
    http.queue(_resp(500), _ok())

    result = notifier.deliver("https://cb.example.com/hook", _payload())

    assert result.delivered is True
    assert result.attempts == 2
    assert result.error is None


def test_network_error_retenta(fake_settings, http):
    http.queue(
        httpx.ConnectError("kaboom", request=httpx.Request("POST", "https://x")),
        _ok(),
    )

    result = notifier.deliver("https://cb.example.com/hook", _payload())

    assert result.delivered is True
    assert result.attempts == 2


def test_timeout_retenta(fake_settings, http):
    http.queue(
        httpx.ConnectTimeout("slow", request=httpx.Request("POST", "https://x")),
        _ok(),
    )

    result = notifier.deliver("https://cb.example.com/hook", _payload())

    assert result.delivered is True
    assert result.attempts == 2


def test_400_nao_retenta(fake_settings, http):
    http.queue(_resp(400))

    result = notifier.deliver("https://cb.example.com/hook", _payload())

    assert result.delivered is False
    assert result.attempts == 1
    assert "400" in result.error


def test_404_nao_retenta(fake_settings, http):
    http.queue(_resp(404))

    result = notifier.deliver("https://cb.example.com/hook", _payload())

    assert result.delivered is False
    assert result.attempts == 1
    assert "404" in result.error


def test_falha_retorna_error_com_tipo_e_mensagem(fake_settings, http):
    http.queue(_resp(500), _resp(500), _resp(500))

    result = notifier.deliver("https://cb.example.com/hook", _payload())

    assert result.error is not None
    assert "HTTPStatusError" in result.error


def test_sucesso_zera_error_field(fake_settings, http):
    http.queue(_resp(500), _ok())

    result = notifier.deliver("https://cb.example.com/hook", _payload())

    assert result.error is None


def test_sign_produz_hmac_sha256_hex():
    signature = notifier._sign(b"hello", "secret")

    expected = hmac.new(b"secret", b"hello", hashlib.sha256).hexdigest()
    assert signature == expected
    assert len(signature) == 64


def test_assinatura_muda_quando_secret_muda():
    a = notifier._sign(b"payload", "secret-a")
    b = notifier._sign(b"payload", "secret-b")

    assert a != b
