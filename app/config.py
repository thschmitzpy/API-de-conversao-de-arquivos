from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str

    celery_broker_url: str
    celery_result_backend: str

    minio_endpoint: str
    minio_public_endpoint: str | None = None
    minio_access_key: str
    minio_secret_key: str
    minio_bucket_input: str = "inputs"
    minio_bucket_output: str = "outputs"
    minio_secure: bool = False
    minio_region: str = "us-east-1"

    webhook_signing_secret: str
    webhook_max_retries: int = 5
    webhook_timeout_seconds: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
