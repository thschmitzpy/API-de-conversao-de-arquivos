from __future__ import annotations

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.database import engine
from app.storage.minio_client import get_client

router = APIRouter(tags=["health"])


class ReadinessChecks(BaseModel):
    postgres: str
    redis: str
    minio: str


class ReadinessResponse(BaseModel):
    status: str
    checks: ReadinessChecks


class LivenessResponse(BaseModel):
    status: str


@router.get(
    "/health",
    response_model=LivenessResponse,
    summary="Liveness probe",
)
def health() -> LivenessResponse:
    return LivenessResponse(status="ok")


def _check_postgres() -> str:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except SQLAlchemyError as exc:
        return f"error: {exc.__class__.__name__}"


def _check_redis() -> str:
    settings = get_settings()
    try:
        client = Redis.from_url(settings.celery_broker_url, socket_timeout=2)
        client.ping()
        return "ok"
    except (RedisError, OSError) as exc:
        return f"error: {exc.__class__.__name__}"


def _check_minio() -> str:
    try:
        get_client().list_buckets()
        return "ok"
    except Exception as exc:
        return f"error: {exc.__class__.__name__}"


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe (Postgres, Redis, MinIO)",
    responses={503: {"description": "Alguma dependencia indisponivel"}},
)
def ready(response: Response) -> ReadinessResponse:
    checks = ReadinessChecks(
        postgres=_check_postgres(),
        redis=_check_redis(),
        minio=_check_minio(),
    )
    ok = all(v == "ok" for v in checks.model_dump().values())
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ok" if ok else "unavailable",
        checks=checks,
    )
