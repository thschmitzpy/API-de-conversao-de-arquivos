from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    FAILED = "FAILED"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"),
        default=JobStatus.PENDING,
        nullable=False,
        index=True,
    )
    operation: Mapped[str] = mapped_column(String(64), nullable=False)

    input_key: Mapped[str] = mapped_column(String(512), nullable=False)
    input_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    input_content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    input_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    output_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    output_content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)

    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    result_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    callback_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    callback_delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    callback_attempts: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Job id={self.id} status={self.status.value} op={self.operation}>"
