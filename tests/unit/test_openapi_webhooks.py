from __future__ import annotations

from app.main import app


def _webhook_spec() -> dict:
    return app.openapi()["webhooks"]["job.finished"]["post"]


def test_webhook_job_finished_usa_webhook_payload():
    body = _webhook_spec()["requestBody"]["content"]["application/json"]

    assert body["schema"]["$ref"].endswith("/WebhookPayload")
    assert set(body["examples"]) == {"completed", "failed"}


def test_webhook_documenta_headers_de_assinatura():
    headers = {p["name"] for p in _webhook_spec()["parameters"] if p["in"] == "header"}

    assert headers == {"x-conversor-signature", "x-conversor-event"}
