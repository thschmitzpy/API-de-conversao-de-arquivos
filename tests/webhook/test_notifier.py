from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

import httpx
import pytest

from app.models import JobStatus
from app.schemas import WebhookPayload
from app.webhook import notifier

URL = "https://cb.example.com/hook"
TIMESTAMP = 1_790_000_000


class _FakeSettings:
    def __init__(self, secret: str = "test-secret", timeout: int = 5):
        self.webhook_signing_secret = secret
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


@pytest.fixture(autouse=True)
def fake_settings(monkeypatch):
    settings = _FakeSettings()
    monkeypatch.setattr(notifier, "get_settings", lambda: settings)
    return settings


@pytest.fixture(autouse=True)
def _relogio_fixo(monkeypatch):
    monkeypatch.setattr(notifier, "_now", lambda: TIMESTAMP)


@pytest.fixture
def http(monkeypatch):
    recorder = _HttpxRecorder()
    _install_fake_client(monkeypatch, recorder)
    return recorder


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


def _resp(status: int) -> httpx.Response:
    return httpx.Response(status_code=status, request=httpx.Request("POST", URL))


def _status_error(status: int) -> httpx.HTTPStatusError:
    response = _resp(status)
    return httpx.HTTPStatusError(str(status), request=response.request, response=response)


def test_send_faz_uma_unica_chamada_com_200(http):
    http.queue(_resp(200))

    notifier.send(URL, _payload())

    assert len(http.calls) == 1
    assert http.calls[0]["url"] == URL


def test_body_enviado_e_json_do_payload(http):
    http.queue(_resp(200))

    notifier.send(URL, _payload())

    sent = json.loads(http.calls[0]["content"].decode("utf-8"))
    assert sent["event"] == "job.completed"
    assert sent["operation"] == "image.thumbnail"


def test_assinatura_cobre_timestamp_e_corpo(http):
    http.queue(_resp(200))

    notifier.send(URL, _payload())

    headers = http.calls[0]["headers"]
    body = http.calls[0]["content"]
    expected = hmac.new(
        b"test-secret", f"{TIMESTAMP}.".encode() + body, hashlib.sha256
    ).hexdigest()
    assert headers["X-Conversor-Timestamp"] == str(TIMESTAMP)
    assert headers["X-Conversor-Signature"] == f"sha256={expected}"


def test_assinatura_so_do_corpo_nao_vale_mais(http):
    http.queue(_resp(200))

    notifier.send(URL, _payload())

    body = http.calls[0]["content"]
    antiga = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    assert http.calls[0]["headers"]["X-Conversor-Signature"] != f"sha256={antiga}"


def test_header_evento_reflete_payload_event(http):
    http.queue(_resp(200))

    notifier.send(URL, _payload(event="job.failed"))

    assert http.calls[0]["headers"]["X-Conversor-Event"] == "job.failed"


def test_content_type_application_json(http):
    http.queue(_resp(200))

    notifier.send(URL, _payload())

    assert http.calls[0]["headers"]["Content-Type"] == "application/json"


def test_user_agent_customizado(http):
    http.queue(_resp(200))

    notifier.send(URL, _payload())

    assert "ConversorArquivos-Webhook" in http.calls[0]["headers"]["User-Agent"]


@pytest.mark.parametrize("status", [400, 404, 500, 503])
def test_status_de_erro_levanta_http_status_error(http, status):
    http.queue(_resp(status))

    with pytest.raises(httpx.HTTPStatusError):
        notifier.send(URL, _payload())

    assert len(http.calls) == 1


@pytest.mark.parametrize(
    ("exc", "esperado"),
    [
        (_status_error(500), True),
        (_status_error(503), True),
        (_status_error(400), False),
        (_status_error(404), False),
        (httpx.ConnectError("kaboom", request=httpx.Request("POST", URL)), True),
        (httpx.ConnectTimeout("slow", request=httpx.Request("POST", URL)), True),
        (ValueError("outro erro"), False),
    ],
)
def test_is_retryable(exc, esperado):
    assert notifier.is_retryable(exc) is esperado


def test_sign_produz_hmac_sha256_hex():
    signature = notifier._sign(b"hello", 123, "secret")

    expected = hmac.new(b"secret", b"123.hello", hashlib.sha256).hexdigest()
    assert signature == expected
    assert len(signature) == 64


def test_assinatura_muda_quando_secret_muda():
    assert notifier._sign(b"payload", 1, "secret-a") != notifier._sign(b"payload", 1, "secret-b")


def test_assinatura_muda_quando_timestamp_muda():
    assert notifier._sign(b"payload", 1, "secret") != notifier._sign(b"payload", 2, "secret")
