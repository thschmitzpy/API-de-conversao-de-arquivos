from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import Body, FastAPI, Header

from app.config import get_settings
from app.schemas import WebhookPayload

_PAYLOAD_EXAMPLES: dict[str, Any] = {
    "completed": {
        "summary": "Job concluido",
        "value": {
            "event": "job.completed",
            "job_id": "3f2b8c1e-7a4d-4e8b-9c1a-2d5e6f7a8b9c",
            "status": "DONE",
            "operation": "image.thumbnail",
            "output_url": "http://localhost:9000/outputs/3f2b8c1e-7a4d-4e8b-9c1a-2d5e6f7a8b9c/output.webp?X-Amz-Signature=...",
            "result_metadata": {"width": 256, "height": 171, "format": "WEBP", "size_bytes": 8412},
            "error_message": None,
            "finished_at": "2026-10-19T14:32:07.512000Z",
        },
    },
    "failed": {
        "summary": "Job falhou",
        "value": {
            "event": "job.failed",
            "job_id": "9a1c4e7b-2f3d-4b6a-8e5c-1d0f2a3b4c5d",
            "status": "FAILED",
            "operation": "pdf.watermark",
            "output_url": None,
            "result_metadata": None,
            "error_message": "ValueError: 'text' obrigatorio e nao pode ser vazio",
            "finished_at": "2026-10-19T14:35:41.087000Z",
        },
    },
}


def _description() -> str:
    settings = get_settings()
    return f"""
    Enviado pelo worker para a `callback_url` informada no `POST /jobs` quando o job
    termina, com sucesso (`job.completed`) ou com erro (`job.failed`).

    ## Verificando a assinatura

    O header `X-Conversor-Signature` contem `sha256=` seguido do HMAC-SHA256 (hex) do
    **corpo bruto** da requisicao, usando o segredo `WEBHOOK_SIGNING_SECRET`:

    ~~~python
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    valido = hmac.compare_digest(expected, request.headers["X-Conversor-Signature"])
    ~~~

    Calcule sobre os bytes recebidos, antes de qualquer parse do JSON.

    ## Entrega e retry

    - Responda com qualquer **2xx** para confirmar o recebimento.
    - **5xx**, timeout ({settings.webhook_timeout_seconds}s) ou erro de rede: nova tentativa
      com backoff exponencial (1s a 30s), ate {settings.webhook_max_retries} tentativas no total.
    - **4xx**: falha definitiva, sem nova tentativa.
    """


def _job_finished(
        payload: Annotated[WebhookPayload, Body(openapi_examples=_PAYLOAD_EXAMPLES)],
        x_conversor_signature: Annotated[
            str,
            Header(description="`sha256=` + HMAC-SHA256 hex do corpo bruto"),
        ],
        x_conversor_event: Annotated[
            Literal["job.completed", "job.failed"],
            Header(description="Mesmo valor do campo `event` do payload"),
        ],
) -> None:
    pass


def register_webhook_docs(app: FastAPI) -> None:
    app.webhooks.add_api_route(
        "job.finished",
        _job_finished,
        methods=["POST"],
        summary="Notificacao de job finalizado",
        description=_description(),
        response_description="Qualquer 2xx confirma o recebimento",
        responses={
            400: {"description": "4xx: falha definitiva, o worker nao tenta de novo"},
            500: {"description": "5xx: o worker tenta de novo com backoff exponencial"},
        },
    )
