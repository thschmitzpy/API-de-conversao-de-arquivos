# ConversorArquivos

API Python/FastAPI de **conversão e processamento assíncrono de arquivos** (imagem, CSV, Excel, PDF, vídeo e áudio), com fila Celery, armazenamento S3-compatível e notificação por webhook assinado.

Projeto de portfólio — foco em arquitetura clara, testes e empacotamento Docker completo.

![CI](https://github.com/thschmitzpy/API-de-conversao-de-arquivos/actions/workflows/ci.yml/badge.svg)

---

## Stack

| Camada | Tecnologia |
|---|---|
| API | FastAPI 0.115 + Uvicorn |
| Fila | Celery 5 + Redis 7 |
| Storage | MinIO (S3-compatível) |
| Banco | Postgres 16 + SQLAlchemy 2.0 (síncrono) + Alembic |
| Processamento | Pillow, pandas, openpyxl, pypdf, FFmpeg |
| Rate limiting | slowapi |
| Observabilidade | Prometheus + Grafana + logs estruturados JSON |
| Testes | pytest (160+ casos, incluindo integração end-to-end) |
| Deploy | Docker Compose |

Python 3.13 · Poetry 1.8

---

## Arquitetura

```
      POST /jobs                send_task                        upload output
┌──────────┐  ───────────────▶ ┌─────────┐  ──────────────────▶ ┌────────┐  ──────────────▶ ┌────────┐
│ Cliente  │                   │   API   │                      │ Worker │                  │ MinIO  │
│          │                   │ FastAPI │                      │ Celery │                  │ (S3)   │
│          │  ◀─────────────── │         │                      │        │  ◀─────────────  │        │
└──────────┘   202 Accepted    └─────────┘                      └────────┘   download input └────────┘
      │        + status_url         │                                │
      │                             ▼                                │
      │                      ┌──────────────┐                        │
      │                      │  Postgres    │  ◀─── atualiza status, metadata, output_key
      │                      │  tabela jobs │
      │                      └──────────────┘
      │
      │  GET /jobs/{id}  ──▶  API devolve status + presigned URL do MinIO
      │
      ▼
┌─────────────┐  ◀─── POST assinado HMAC-SHA256 (se callback_url informado)
│ callback_url│       retry exponencial via tenacity
└─────────────┘
```

Fluxo:

1. Cliente envia arquivo + `operation` + `parameters` (JSON) → `POST /jobs`.
2. API valida tamanho/formato, salva o input no MinIO, cria a linha em `jobs` e enfileira a task Celery. Devolve `202 Accepted` com `job_id` e `status_url`.
3. Worker consome a fila, baixa o input, chama o processor correspondente e salva o output no MinIO.
4. Worker atualiza o `Job` no Postgres (status, `output_key`, `result_metadata`, `finished_at`).
5. Se o cliente informou `callback_url`, worker dispara webhook assinado com HMAC-SHA256 (retry exponencial).
6. Cliente consulta `GET /jobs/{id}` e recebe URL presigned para baixar o output direto do storage.

---

## Operações suportadas

| `operation` | Entrada | Saída | Parâmetros principais |
|---|---|---|---|
| `image.thumbnail` | PNG / JPEG / WEBP / GIF | mesmo formato (ou `format` escolhido) | `width`, `height`, `format`, `quality` |
| `csv.validate` | CSV | relatório JSON | `columns` (schema declarativo), `delimiter`, `has_header`, `encoding`, `mode` |
| `excel.to-csv` | XLSX | CSV | `sheet` (nome ou índice), `delimiter`, `encoding`, `include_header` |
| `pdf.extract-text` | PDF | TXT ou JSON | `pages` (ex: `"1-3,5"`), `output_format` (`text` ou `json`) |
| `pdf.merge` | ZIP de PDFs | PDF único | `order` (lista de nomes; se ausente, ordem alfabética) |
| `video.transcode` | qualquer vídeo | MP4 ou WebM | `format`, `resolution` (`480p`/`720p`/`1080p`), `crf` (18-28), `strip_audio` |
| `audio.extract` | áudio ou vídeo | MP3 / WAV / OGG / AAC | `format`, `bitrate`, `sample_rate`, `channels` |

Limite de upload: **100 MB** por job.

---

## Como rodar

Pré-requisitos: Docker Desktop (ou Docker Engine) + Compose v2.

```bash
cp .env.example .env         # ajuste segredos se quiser
docker compose up -d --build
```

Isso sobe 7 containers: `api`, `worker`, `postgres`, `redis`, `minio`, `prometheus` e `grafana`. A API aplica as migrations Alembic no startup.

Endpoints disponíveis:

- **API** — http://localhost:8000
- **Swagger UI** — http://localhost:8000/docs
- **Health / Readiness** — http://localhost:8000/health e http://localhost:8000/ready
- **Métricas Prometheus** — http://localhost:8000/metrics (API) e http://localhost:9100 (worker)
- **Grafana** — http://localhost:3000 (login `admin/admin`, dashboard "ConversorArquivos" pré-provisionado)
- **Prometheus** — http://localhost:9090
- **Console MinIO** — http://localhost:9001 (usuário/senha: `minioadmin` / `minioadmin`)
- **Postgres** — `localhost:5434` (usuário/senha/db: `conversor`)

Para parar:

```bash
docker compose down            # mantém os volumes (banco e storage)
docker compose down -v         # também apaga os volumes
```

---

## Exemplos de uso

### 1. Criar um job de thumbnail

```bash
curl -X POST http://localhost:8000/jobs \
  -F "file=@foto.jpg" \
  -F "operation=image.thumbnail" \
  -F 'parameters={"width": 300, "height": 300, "format": "WEBP", "quality": 80}'
```

Resposta (`202 Accepted`):

```json
{
  "id": "9a7b1c2d-3e4f-5061-7283-94a5b6c7d8e9",
  "status": "pending",
  "status_url": "http://localhost:8000/jobs/9a7b1c2d-3e4f-5061-7283-94a5b6c7d8e9"
}
```

### 2. Consultar o status

```bash
curl http://localhost:8000/jobs/9a7b1c2d-3e4f-5061-7283-94a5b6c7d8e9
```

Resposta (job concluído):

```json
{
  "id": "9a7b1c2d-...",
  "status": "completed",
  "operation": "image.thumbnail",
  "input_filename": "foto.jpg",
  "output_url": "http://localhost:9000/outputs/9a7b.../output.webp?X-Amz-Signature=...",
  "result_metadata": {"width": 300, "height": 300, "format": "WEBP"},
  "created_at": "2026-10-01T18:00:00Z",
  "finished_at": "2026-10-01T18:00:02Z"
}
```

### 3. Listar jobs com filtros

```bash
curl "http://localhost:8000/jobs?status=completed&operation=image.thumbnail&limit=10&offset=0"
```

Resposta:

```json
{
  "items": [ /* ... JobSummary ... */ ],
  "total": 42,
  "limit": 10,
  "offset": 0
}
```

### 4. Receber webhook ao concluir

Passe `-F "callback_url=https://seu-endpoint/..."` no `POST /jobs`. Ao finalizar, o worker envia `POST` no endpoint com o payload JSON do resultado, assinado no header `X-Signature` usando HMAC-SHA256 e o segredo `WEBHOOK_SIGNING_SECRET` do `.env`. Em caso de falha HTTP, o notifier faz retry exponencial via tenacity.

---

## Rate limiting

Por padrão (configurável no `.env`):

- `POST /jobs` — **10 requisições/minuto por IP**
- `GET /jobs/{id}` e `GET /jobs` — **60 requisições/minuto por IP**

Quando excedido, a API responde `429 Too Many Requests`.

---

## Observabilidade

A API e o worker expõem três camadas de observabilidade — todas prontas no `docker compose up`, sem configuração adicional.

### Health checks

- `GET /health` — liveness: responde `200 OK` enquanto o processo está de pé.
- `GET /ready` — readiness: verifica Postgres (`SELECT 1`), Redis (`PING`) e MinIO (`list_buckets`). Devolve `200` com `{"status":"ready"}` quando tudo responde, ou `503 Service Unavailable` detalhando qual dependência caiu.

Nenhuma das rotas passa pelo rate limiter — seguras para probes de orquestrador.

### Métricas Prometheus

A API expõe `/metrics` via `prometheus-fastapi-instrumentator`. O worker Celery expõe suas próprias métricas em um HTTP server na porta **9100**, iniciado no signal `worker_ready`.

Métricas de negócio (em `app/metrics.py`, compartilhadas entre API e worker):

| Métrica | Labels | Descrição |
|---|---|---|
| `jobs_created_total` | `operation` | Jobs criados por tipo de operação |
| `jobs_finished_total` | `operation`, `status` | Jobs finalizados (`done` / `failed` / `unsupported`) |
| `job_processing_seconds` | `operation` | Histograma do tempo de processamento (0.1s → 300s) |

Além dessas, o instrumentator exporta `http_requests_total` e `http_request_duration_seconds_bucket` — excluindo `/metrics`, `/health` e `/ready` do próprio tráfego medido.

### Dashboard Grafana

O compose provisiona o Grafana com datasource Prometheus e um dashboard pré-carregado — abra http://localhost:3000 e procure por **ConversorArquivos**. Quatro painéis:

1. **RPS por endpoint (API)** — taxa por `handler`.
2. **Latência p95 por endpoint (API)** — `histogram_quantile(0.95, ...)` sobre o bucket de duração.
3. **Jobs criados por operation** — stacked.
4. **Jobs finalizados por status** — stacked, cores fixas (verde `done`, vermelho `failed`, laranja `unsupported`).

Prometheus (http://localhost:9090) retém 7 dias no volume `conversor-prometheus`.

### Logs estruturados JSON

Toda saída de log — API, worker, Uvicorn e Celery — é renderizada em JSON single-line, pronta para Loki, Elastic ou Datadog. Cada linha carrega `timestamp` (ISO 8601 com timezone), `level`, `logger`, `message` e campos estruturados injetados via `extra={...}`.

Os call sites de processamento injetam `job_id` e `operation` como campos top-level — você filtra `job_id="abc-123"` direto no backend de logs em vez de regex em texto livre:

```json
{"timestamp":"2026-10-05T18:00:02.431Z","level":"INFO","logger":"app.workers.tasks","message":"Job concluido","job_id":"abc-123","operation":"image.thumbnail"}
```

Configuração em `app/logging_setup.py` (`ConversorJsonFormatter` + `configure_logging()`). A API chama o setup antes de instanciar o FastAPI; o worker, via signal `setup_logging` do Celery.

---

## Testes

O setup é **dual-container**: as dependências de desenvolvimento estão instaladas tanto no `api` quanto no `worker`, mas apenas o `worker` tem o FFmpeg instalado. Por isso os testes de vídeo e áudio rodam no `worker` e o restante no `api`.

Processors sem FFmpeg + webhook + rate limit + integração (container `api`):

```bash
docker compose run --rm --no-deps --entrypoint="" api pytest tests/ -v \
  --ignore=tests/processors/test_video_transcode.py \
  --ignore=tests/processors/test_audio_extract.py
```

Processors FFmpeg — vídeo e áudio (container `worker`):

```bash
docker compose run --rm --no-deps --entrypoint="" worker pytest \
  tests/processors/test_video_transcode.py \
  tests/processors/test_audio_extract.py -v
```

> No PowerShell, use `--entrypoint=""` com o sinal de igual — sem ele o PS descarta a string vazia.

Cobertura atual: **160+ testes** em 10 suites — processors (unit), webhook (com e sem retry), rate limit e integração end-to-end (POST → worker → GET → MinIO).

---

## Integração contínua

O workflow `.github/workflows/ci.yml` roda a cada push e pull request na branch `main`, com dois jobs:

- **`lint`** — Ruff check sobre todo o código.
- **`test`** — sobe Postgres, Redis e MinIO via `docker compose`, instala Python 3.13 + Poetry + FFmpeg no runner, aplica migrations Alembic, inicia o worker Celery em background e executa toda a suite `pytest`.

Em caso de falha, o step final despeja o `celery.log` para facilitar o diagnóstico.

---

## Estrutura do projeto

```
app/
├── api/              Endpoints HTTP (jobs.py)
├── broker/           Fábrica da app Celery
├── storage/          Cliente MinIO (upload, presigned, ensure_buckets)
├── webhook/          Notifier HMAC + retry
├── workers/          Celery tasks + processors
│   └── processors/   image, csv, excel, pdf (extract/merge), video, audio
├── config.py         Settings via pydantic-settings
├── database.py       SessionLocal / get_db
├── main.py           FastAPI app + lifespan (ensure_buckets com retry)
├── models.py         ORM (Job, JobStatus)
├── rate_limit.py     Limiter slowapi
└── schemas.py        Pydantic DTOs
migrations/           Alembic
tests/
├── processors/       Testes unitários dos processors
├── integration/      End-to-end contra Postgres/Redis/MinIO reais do compose
├── webhook/          Notifier + retry
└── rate_limit/       Comportamento do slowapi
```

---

## Decisões de design

- **Celery + Redis** em vez de `BackgroundTasks` do FastAPI — jobs sobrevivem a restart da API e o worker escala horizontalmente de forma independente.
- **MinIO** no lugar de S3 real — mesmo contrato S3, 100% offline, ideal para portfólio e desenvolvimento local.
- **Postgres `jobs` como fonte da verdade** — status, parâmetros, metadados e resultado ficam no banco. O Celery só carrega o `job_id`, evitando payloads grandes na fila.
- **Presigned URL** para o cliente baixar o output direto do storage — a API não vira proxy de arquivo.
- **Webhook com HMAC-SHA256** — o cliente consegue validar criptograficamente que o payload veio deste serviço.
- **Dois endpoints MinIO** (`MINIO_ENDPOINT` interno para API/worker; `MINIO_PUBLIC_ENDPOINT` para o host da URL presigned) — resolve o problema clássico de assinatura S3 em ambiente Docker, onde o nome do serviço interno não resolve do browser.
- **SQLAlchemy síncrono** — o Celery worker é síncrono e manter o mesmo paradigma na API elimina complexidade de bridges async/sync.
- **Enum Postgres explícito** para `job_status` — criado na migration, mais confiável do que depender da criação automática pelo SQLAlchemy.

---

## Licença

Projeto pessoal de portfólio, sem fins comerciais.
