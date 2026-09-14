from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import JobStatus


class JobCreateResponse(BaseModel):
    id: uuid.UUID
    status: JobStatus
    status_url: str


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: JobStatus
    operation: str

    input_filename: str
    input_content_type: str
    input_size_bytes: int

    output_key: str | None = None
    output_content_type: str | None = None
    output_url: str | None = None

    parameters: dict[str, Any] = Field(default_factory=dict)
    result_metadata: dict[str, Any] | None = None

    error_message: str | None = None

    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class WebhookPayload(BaseModel):
    event: Literal["job.completed", "job.failed"]
    job_id: uuid.UUID
    status: JobStatus
    operation: str
    output_url: str | None = None
    result_metadata: dict[str, Any] | None = None
    error_message: str | None = None
    finished_at: datetime


class ErrorResponse(BaseModel):
    detail: str
