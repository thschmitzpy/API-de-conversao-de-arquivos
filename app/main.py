from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from tenacity import retry, stop_after_attempt, wait_fixed

from app.api.jobs import router as jobs_router
from app.rate_limit import limiter
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

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(jobs_router)
