from __future__ import annotations

import io
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from minio.error import S3Error
from PIL import Image
from sqlalchemy import text

from app.config import get_settings
from app.database import SessionLocal
from app.main import app
from app.storage.minio_client import ensure_buckets, get_client


@pytest.fixture(scope="session", autouse=True)
def _ensure_buckets_up() -> None:
    ensure_buckets()


@pytest.fixture(autouse=True)
def _clean_state() -> Generator[None, None, None]:
    _truncate_jobs()
    settings = get_settings()
    _empty_bucket(settings.minio_bucket_input)
    _empty_bucket(settings.minio_bucket_output)
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _truncate_jobs() -> None:
    with SessionLocal() as db:
        db.execute(text("TRUNCATE TABLE jobs CASCADE"))
        db.commit()


def _empty_bucket(bucket: str) -> None:
    minio = get_client()
    names = [obj.object_name for obj in minio.list_objects(bucket, recursive=True)]
    for name in names:
        minio.remove_object(bucket, name)


def make_png_bytes(size: int = 100, color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), color=color).save(buf, format="PNG")
    return buf.getvalue()


def object_exists(bucket: str, key: str) -> bool:
    try:
        get_client().stat_object(bucket, key)
        return True
    except S3Error:
        return False
