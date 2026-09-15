from __future__ import annotations

import io
from datetime import timedelta
from functools import lru_cache
from typing import BinaryIO

from minio import Minio

from app.config import get_settings


@lru_cache
def get_client() -> Minio:
    settings = get_settings()
    return Minio(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
        region=settings.minio_region,
    )


@lru_cache
def get_public_client() -> Minio:
    settings = get_settings()
    endpoint = settings.minio_public_endpoint or settings.minio_endpoint
    return Minio(
        endpoint=endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
        region=settings.minio_region,
    )


def ensure_buckets() -> None:
    settings = get_settings()
    client = get_client()
    for bucket in (settings.minio_bucket_input, settings.minio_bucket_output):
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)


def upload_stream(
    bucket: str,
    key: str,
    stream: BinaryIO,
    size: int,
    content_type: str,
) -> None:
    get_client().put_object(
        bucket_name=bucket,
        object_name=key,
        data=stream,
        length=size,
        content_type=content_type,
    )


def download_bytes(bucket: str, key: str) -> io.BytesIO:
    response = get_client().get_object(bucket, key)
    try:
        buffer = io.BytesIO(response.read())
    finally:
        response.close()
        response.release_conn()
    buffer.seek(0)
    return buffer


def presigned_get_url(bucket: str, key: str, expires_seconds: int = 3600) -> str:
    return get_public_client().presigned_get_object(
        bucket_name=bucket,
        object_name=key,
        expires=timedelta(seconds=expires_seconds),
    )


def delete_object(bucket: str, key: str) -> None:
    get_client().remove_object(bucket, key)
