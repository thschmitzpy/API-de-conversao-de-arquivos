from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

import httpx
from celery.utils.log import get_task_logger
from tenacity import (
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.schemas import WebhookPayload

logger = get_task_logger(__name__)


@dataclass
class WebhookDelivery:
    delivered: bool
    attempts: int
    error: str | None = None


def _should_retry(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def deliver(callback_url: str, payload: WebhookPayload) -> WebhookDelivery:
    settings = get_settings()

    body = payload.model_dump_json().encode("utf-8")
    signature = _sign(body, settings.webhook_signing_secret)

    headers = {
        "Content-Type": "application/json",
        "X-Conversor-Signature": f"sha256={signature}",
        "X-Conversor-Event": payload.event,
        "User-Agent": "ConversorArquivos-Webhook/1.0",
    }

    attempts = 0

    try:
        for attempt in Retrying(
            stop=stop_after_attempt(settings.webhook_max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=30),
            retry=retry_if_exception(_should_retry),
            reraise=True,
        ):
            with attempt:
                attempts += 1
                with httpx.Client(timeout=settings.webhook_timeout_seconds) as client:
                    response = client.post(callback_url, content=body, headers=headers)
                    response.raise_for_status()
        return WebhookDelivery(delivered=True, attempts=attempts)

    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        return WebhookDelivery(delivered=False, attempts=attempts, error=error)
