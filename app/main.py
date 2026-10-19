from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, Response
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from tenacity import retry, stop_after_attempt, wait_fixed

from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.config import get_settings
from app.logging_setup import configure_logging
from app.rate_limit import limiter
from app.storage.minio_client import ensure_buckets
from app.webhook.openapi import register_webhook_docs

configure_logging()

_settings = get_settings()

API_DESCRIPTION = f"""
  API de conversao e processamento assincrono de arquivos: imagem, CSV, Excel,
  PDF, documentos Office, video e audio.

  ## Fluxo

  1. **`POST /jobs`** envia o arquivo (multipart) com a `operation` desejada e,
     opcionalmente, `parameters` (JSON) e `callback_url`. Retorna `202 Accepted`
     com o `id` do job e a `status_url`.
  2. O worker Celery processa o arquivo em background.
  3. Acompanhe o resultado de uma das formas:
     - **Polling** em `GET /jobs/{{id}}` ate o status virar `done` ou `failed`.
       Quando `done`, `output_url` traz um link temporario para download.
     - **Webhook**: se `callback_url` foi informada, a API envia um `POST` com o
         resultado, assinado com HMAC-SHA256 no header `X-Conversor-Signature`.
         Payload, verificacao e regras de retry na secao **Webhooks** no fim da pagina.

  ## Autenticacao

  Todas as rotas de `/jobs` exigem o header **`X-API-Key`**. Clique em
  **Authorize** e informe uma das chaves definidas em `API_KEYS`.
  Sem header: `401`. Chave invalida: `403`.

  ## Rate limiting

  | Rota | Limite |
  |---|---|
  | `POST /jobs` | {_settings.rate_limit_create_job} |
  | `GET /jobs` e `GET /jobs/{{id}}` | {_settings.rate_limit_get_job} |

  Excedido o limite, a resposta e `429 Too Many Requests`. Os headers
  `X-RateLimit-*` informam o consumo da janela atual.
  """

OPENAPI_TAGS = [
    {
        "name": "jobs",
        "description": "Criacao, consulta e listagem de jobs de processamento. "
                       "Exige `X-API-Key`.",
    },
    {
        "name": "health",
        "description": "Probes de liveness e readiness para orquestradores. "
                       "Publicas, sem autenticacao e fora do rate limit.",
    },
]


@retry(stop=stop_after_attempt(30), wait=wait_fixed(2), reraise=True)
def _wait_minio_ready() -> None:
    ensure_buckets()


@asynccontextmanager
async def lifespan(_: FastAPI):
    _wait_minio_ready()
    yield


app = FastAPI(
    title="Conversor de Arquivos",
    version="0.1.0",
    description=API_DESCRIPTION,
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
    response = JSONResponse(
        {"detail": f"Limite de requisicoes excedido: {exc.detail}"},
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    )
    return request.app.state.limiter._inject_headers(
        response, request.state.view_rate_limit
    )


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)

Instrumentator(
    excluded_handlers=["/metrics", "/health", "/ready"],
).instrument(app).expose(app, include_in_schema=False)

app.include_router(health_router)
app.include_router(jobs_router)
register_webhook_docs(app)
