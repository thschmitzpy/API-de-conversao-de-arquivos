# ConversorArquivos

API Python/FastAPI de **conversão e processamento assíncrono de arquivos** (imagem, CSV, Excel, PDF, vídeo e áudio), com fila Celery, armazenamento S3-compatível e notificação por webhook assinado.

Projeto de portfólio — foco em arquitetura clara, testes, empacotamento Docker completo e deploy em Kubernetes.

![CI](https://github.com/thschmitzpy/API-de-conversao-de-arquivos/actions/workflows/ci.yml/badge.svg)

---

## Stack

| Camada | Tecnologia |
|---|---|
| API | FastAPI 0.115 + Uvicorn |
| Fila | Celery 5 + Redis 7 |
| Storage | MinIO (S3-compatível) |
| Banco | Postgres 16 + SQLAlchemy 2.0 (síncrono) + Alembic |
| Processamento | Pillow, pandas, openpyxl, pypdf, FFmpeg, Tesseract, LibreOffice headless |
| Rate limiting | slowapi |
| Observabilidade | Prometheus + Grafana + logs estruturados JSON |
| Testes | pytest (250+ casos, incluindo integração end-to-end) |
| Deploy | Docker Compose · Kubernetes (Kustomize) |

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
| `pdf.watermark` | PDF | PDF com marca d'água | `text`, `position` (`diagonal`/`center`/`footer`/`header`), `opacity` (0–1), `font_size`, `color` (`gray`/`black`/`red`/`blue`) |
| `video.transcode` | qualquer vídeo | MP4 ou WebM | `format`, `resolution` (`480p`/`720p`/`1080p`), `crf` (18-28), `strip_audio` |
| `audio.extract` | áudio ou vídeo | MP3 / WAV / OGG / AAC | `format`, `bitrate`, `sample_rate`, `channels` |
| `ocr.extract` | PDF ou imagem (PNG/JPEG/WEBP/GIF) | TXT ou JSON | `lang` (`eng`, `por`, `por+eng`, …), `output_format` (`text` ou `json`), `dpi` (72-600, só para PDF) |
| `document.convert` | DOCX / DOC / ODT / RTF / XLSX / XLS / ODS / PPTX / PPT / ODP | PDF | — (formato detectado pelo conteúdo, não pela extensão) |

Limite de upload: **100 MB** por job.

Uma `operation` fora da lista é rejeitada com `422 Unprocessable Entity` antes de qualquer upload ou gravação no banco; a resposta lista as operações aceitas. A lista vem do enum `Operation` (`app/operations.py`), compartilhado entre API e worker — um teste unitário garante que todo valor do enum tem processor registrado e vice-versa. No Swagger (`/docs`), o campo `operation` aparece como dropdown.

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

## Kubernetes

O mesmo stack roda num cluster Kubernetes local, descrito com Kustomize em `k8s/`. O alvo é o Kubernetes embutido no Docker Desktop (modo **kind**, v1.34): os Services `LoadBalancer` respondem em `localhost`, então as URLs são as mesmas do compose.

Pré-requisitos: Docker Desktop com Kubernetes habilitado (Settings → Kubernetes → kind) e `kubectl` apontando para o contexto dele.

```powershell
docker compose stop                                   # o cluster usa as mesmas portas
Copy-Item k8s/secrets.env.example k8s/secrets.env     # segredos locais, fora do git
./k8s/load-images.ps1                                 # builda api/worker e importa no nó do kind
kubectl apply -k k8s
kubectl -n conversor get pods -w
```

O nó do kind tem um containerd próprio e não enxerga as imagens do Docker local. Por isso os manifests usam `imagePullPolicy: Never` e o `load-images.ps1` builda, exporta (`docker save`) e importa as imagens direto no nó. Depois de alterar código:

```powershell
./k8s/load-images.ps1
kubectl -n conversor rollout restart deploy/api deploy/worker
```

API (8000), MinIO (9000/9001), Grafana (3000) e Prometheus (9090) ficam nas mesmas portas do compose. O Postgres fica só dentro do cluster:

```powershell
kubectl -n conversor port-forward svc/postgres 5434:5432
```

| Componente | Recursos | Detalhes |
|---|---|---|
| `api` | Deployment (1 réplica) + LoadBalancer 8000 | initContainer roda `alembic upgrade head`; startup/liveness em `/health`, readiness em `/ready` |
| `worker` | Deployment (2 réplicas) + Service headless | `terminationGracePeriodSeconds: 120` para terminar o job em andamento antes de sair |
| `postgres` | StatefulSet + PVC 1Gi | Service ClusterIP |
| `minio` | StatefulSet + PVC 5Gi + LoadBalancer 9000/9001 | mesmo `MINIO_PUBLIC_ENDPOINT=localhost:9000` do compose |
| `redis` | Deployment | sem persistência — broker, result backend e storage do rate limit |
| `prometheus` | StatefulSet + PVC 2Gi + LoadBalancer 9090 | descobre cada pod do worker via DNS do Service headless |
| `grafana` | Deployment + LoadBalancer 3000 | sem PVC — datasource e dashboard vêm de ConfigMaps |

A config não sensível vem de um `configMapGenerator` e os segredos de um `secretGenerator` lido de `k8s/secrets.env`. O sufixo de hash que o Kustomize põe nos nomes faz os pods serem recriados sozinhos quando a config muda.

Para remover tudo, inclusive volumes:

```powershell
kubectl delete -k k8s
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

Passe `-F "callback_url=https://seu-endpoint/..."` no `POST /jobs`. Ao finalizar, o worker envia `POST` no endpoint com o payload JSON do resultado, assinado no header `X-Conversor-Signature` (`sha256=<hmac hex>`) usando HMAC-SHA256 sobre o corpo bruto e o segredo `WEBHOOK_SIGNING_SECRET` do `.env`. Respostas 5xx, timeout e erros de rede disparam retry exponencial via tenacity; 4xx é tratado como falha definitiva. O formato completo do payload, com exemplos, está na seção **Webhooks** do `/docs`.

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

Processors que dependem de binários de sistema — FFmpeg, Tesseract e LibreOffice (container `worker`):

```bash
docker compose run --rm --no-deps --entrypoint="" worker pytest \
  tests/processors/test_video_transcode.py \
  tests/processors/test_audio_extract.py \
  tests/processors/test_ocr_extract.py \
  tests/processors/test_document_convert.py -v
```

> No PowerShell, use `--entrypoint=""` com o sinal de igual — sem ele o PS descarta a string vazia.

Cobertura atual: **250+ testes** em 19 suites — processors (unit), webhook (com e sem retry), rate limit e integração end-to-end (POST → worker → GET → MinIO).

---

## Integração contínua

O workflow `.github/workflows/ci.yml` roda a cada push e pull request na branch `main`, com três jobs:

- **`lint`** — Ruff check sobre todo o código.
- **`test`** — sobe Postgres, Redis e MinIO via `docker compose`, instala Python 3.13 + Poetry e os binários de sistema dos processors (FFmpeg, Tesseract com `eng`/`por` e LibreOffice headless) no runner, aplica migrations Alembic, inicia o worker Celery em background e executa toda a suite `pytest`.
- **`k8s`** — renderiza os manifests com `kubectl kustomize k8s` e valida o resultado com [kubeconform](https://github.com/yannh/kubeconform) em modo `-strict` (campo desconhecido ou com tipo errado reprova o build). Antes disso, compara os arquivos do Grafana em `monitoring/` com as cópias em `k8s/monitoring/`.

As cópias existem porque o Kustomize não lê arquivos fora do diretório da kustomization. Sem a verificação, mexer no dashboard do compose e esquecer da cópia faria os dois ambientes divergirem sem nenhum erro aparente.

Os testes de vídeo, áudio, OCR e conversão de documentos usam `skipif` quando o binário correspondente não existe — útil localmente, perigoso no CI, porque uma instalação quebrada transformaria falhas em testes pulados sem ninguém notar. Por isso o step **Verify system binaries** chama `ffmpeg`, `tesseract` e `soffice` antes da suite: se algum faltar, o pipeline falha ali, e o badge verde significa que **todos** os processors foram de fato exercitados.

Em caso de falha, o step final despeja o `celery.log` para facilitar o diagnóstico.

---

## Estrutura do projeto

```
app/
├── api/              Endpoints HTTP (jobs.py, health.py)
├── broker/           Fábrica da app Celery
├── storage/          Cliente MinIO (upload, presigned, ensure_buckets)
├── webhook/          Notifier HMAC + retry
├── workers/          Celery tasks + processors
│   └── processors/   image, csv, excel, pdf (extract/merge/watermark), video, audio, ocr, document
├── auth.py           Validação do header X-API-Key
├── config.py         Settings via pydantic-settings
├── database.py       SessionLocal / get_db
├── logging_setup.py  Formatter JSON + configure_logging()
├── main.py           FastAPI app + lifespan (ensure_buckets com retry)
├── metrics.py        Métricas Prometheus de negócio (API + worker)
├── models.py         ORM (Job, JobStatus)
├── operations.py     Enum Operation (fonte única das operações aceitas)
├── rate_limit.py     Limiter slowapi
└── schemas.py        Pydantic DTOs
k8s/                  Manifests Kustomize (api, worker, postgres, redis, minio, prometheus, grafana)
├── monitoring/       Configs do Prometheus/Grafana para o cluster
└── load-images.ps1   Build + import das imagens no nó do kind
migrations/           Alembic
monitoring/           Configs do Prometheus/Grafana para o compose
tests/
├── processors/       Testes unitários dos processors
├── integration/      End-to-end contra Postgres/Redis/MinIO reais do compose
├── unit/             Logging JSON + consistência enum Operation × processors
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
- **Detecção de formato por conteúdo** em `ocr.extract` e `document.convert` — magic bytes e estrutura interna (streams OLE2, diretórios OOXML, `mimetype` ODF) em vez de confiar na extensão ou no `content_type` do upload.
- **LibreOffice com perfil isolado por job** (`-env:UserInstallation` em diretório temporário) — com `--concurrency=2`, duas instâncias no perfil padrão se bloqueiam e a segunda sai sem converter. O `soffice` roda em sessão própria para que o timeout mate o grupo inteiro de processos, sem deixar `soffice.bin` órfão.
- **Enum Postgres explícito** para `job_status` — criado na migration, mais confiável do que depender da criação automática pelo SQLAlchemy.
- **Migration em initContainer** no Kubernetes — o Alembic roda antes do container da API subir, e a API fica com 1 réplica porque duas migrations concorrentes no mesmo banco disputariam o lock da `alembic_version`.
- **Métricas do worker em modo multiprocess** — com o pool prefork do Celery, as tasks rodam nos processos filhos, mas o HTTP server de métricas fica no pai. Com `PROMETHEUS_MULTIPROC_DIR`, cada filho grava as métricas em arquivo e o `MultiProcessCollector` soma tudo no scrape. Sem isso, `jobs_finished_total` e `job_processing_seconds` nunca apareciam.
- **Prometheus com `dns_sd_configs` no Service headless do worker** — cada réplica vira um target próprio. Um target estático `worker:9100` cairia em um pod aleatório a cada scrape.

---

## Licença

Projeto pessoal de portfólio, sem fins comerciais.
