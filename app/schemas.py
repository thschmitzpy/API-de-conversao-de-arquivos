from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import JobStatus

_STATUS_DESCRIPTION = "Ciclo de vida: PENDING -> PROCESSING -> DONE ou FAILED"

_JOB_ID_EXAMPLE = "3f2b8c1e-7a4d-4e8b-9c1a-2d5e6f7a8b9c"

_JOB_STATUS_EXAMPLE: dict[str, Any] = {
    "id": _JOB_ID_EXAMPLE,
    "status": "DONE",
    "operation": "image.thumbnail",
    "input_filename": "foto.jpg",
    "input_content_type": "image/jpeg",
    "input_size_bytes": 482133,
    "output_key": f"{_JOB_ID_EXAMPLE}/output.webp",
    "output_content_type": "image/webp",
    "output_url": f"http://localhost:9000/outputs/{_JOB_ID_EXAMPLE}/output.webp?X-Amz-Signature=...",
    "parameters": {"width": 256, "height": 256, "format": "webp"},
    "result_metadata": {"width": 256, "height": 171, "format": "WEBP", "size_bytes": 8412},
    "error_message": None,
    "created_at": "2026-10-19T14:32:05.104000Z",
    "updated_at": "2026-10-19T14:32:07.512000Z",
    "started_at": "2026-10-19T14:32:05.380000Z",
    "finished_at": "2026-10-19T14:32:07.512000Z",
}

_JOB_SUMMARY_EXAMPLE: dict[str, Any] = {
    key: _JOB_STATUS_EXAMPLE[key]
    for key in (
        "id",
        "status",
        "operation",
        "input_filename",
        "input_size_bytes",
        "error_message",
        "created_at",
        "updated_at",
        "finished_at",
    )
}


class JobCreateResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": _JOB_ID_EXAMPLE,
                    "status": "PENDING",
                    "status_url": f"http://localhost:8000/jobs/{_JOB_ID_EXAMPLE}",
                }
            ]
        }
    )

    id: uuid.UUID
    status: JobStatus = Field(description=_STATUS_DESCRIPTION)
    status_url: str = Field(description="URL do GET /jobs/{id} para acompanhar o job")


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"examples": [_JOB_STATUS_EXAMPLE]},
    )

    id: uuid.UUID
    status: JobStatus = Field(description=_STATUS_DESCRIPTION)
    operation: str

    input_filename: str
    input_content_type: str
    input_size_bytes: int

    output_key: str | None = None
    output_content_type: str | None = None
    output_url: str | None = Field(
        default=None,
        description="Link presigned para download do resultado, valido por 1 hora. "
                    "Presente apenas quando status = DONE.",
    )

    parameters: dict[str, Any] = Field(default_factory=dict)
    result_metadata: dict[str, Any] | None = None

    error_message: str | None = None

    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class JobSummary(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"examples": [_JOB_SUMMARY_EXAMPLE]},
    )

    id: uuid.UUID
    status: JobStatus = Field(description=_STATUS_DESCRIPTION)
    operation: str

    input_filename: str
    input_size_bytes: int

    error_message: str | None = None

    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None


class JobListResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"items": [_JOB_SUMMARY_EXAMPLE], "total": 1, "limit": 20, "offset": 0}
            ]
        }
    )

    items: list[JobSummary]
    total: int
    limit: int
    offset: int


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
    detail: str = Field(description="Mensagem legivel descrevendo o erro")
