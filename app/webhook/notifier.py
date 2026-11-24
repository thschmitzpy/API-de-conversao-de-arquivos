from __future__ import annotations

import hashlib
import hmac
import time

import httpx

from app.config import get_settings
from app.schemas import WebhookPayload


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


def _now() -> int:
    return int(time.time())


def _sign(body: bytes, timestamp: int, secret: str) -> str:
    message = f"{timestamp}.".encode("utf-8") + body
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def send(callback_url: str, payload: WebhookPayload) -> None:
    settings = get_settings()

    body = payload.model_dump_json().encode("utf-8")
    timestamp = _now()
    signature = _sign(body, timestamp, settings.webhook_signing_secret)

    headers = {
        "Content-Type": "application/json",
        "X-Conversor-Signature": f"sha256={signature}",
        "X-Conversor-Timestamp": str(timestamp),
        "X-Conversor-Event": payload.event,
        "User-Agent": "ConversorArquivos-Webhook/1.0",
    }

    with httpx.Client(timeout=settings.webhook_timeout_seconds) as client:
        response = client.post(callback_url, content=body, headers=headers)
        response.raise_for_status()
