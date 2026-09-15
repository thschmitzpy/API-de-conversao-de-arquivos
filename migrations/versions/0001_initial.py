from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    job_status = postgresql.ENUM(
        "PENDING",
        "PROCESSING",
        "DONE",
        "FAILED",
        name="job_status",
        create_type=False,
    )
    job_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", job_status, nullable=False),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("input_key", sa.String(512), nullable=False),
        sa.Column("input_filename", sa.String(255), nullable=False),
        sa.Column("input_content_type", sa.String(128), nullable=False),
        sa.Column("input_size_bytes", sa.Integer(), nullable=False),
        sa.Column("output_key", sa.String(512), nullable=True),
        sa.Column("output_content_type", sa.String(128), nullable=True),
        sa.Column(
            "parameters",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("result_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("callback_url", sa.String(2048), nullable=True),
        sa.Column("callback_delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "callback_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_table("jobs")
    postgresql.ENUM(name="job_status").drop(op.get_bind(), checkfirst=True)
