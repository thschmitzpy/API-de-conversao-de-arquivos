from contextlib import asynccontextmanager

from fastapi import FastAPI
from tenacity import retry, stop_after_attempt, wait_fixed

from app.api.jobs import router as jobs_router
from app.storage.minio_client import ensure_buckets


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
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(jobs_router)
