from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_files_purged_at"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("files_purged_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Indice parcial: so os jobs que ainda tem arquivos, ordenados como a limpeza consulta.
    op.create_index(
        "ix_jobs_finished_at_not_purged",
        "jobs",
        ["finished_at"],
        postgresql_where=sa.text("files_purged_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_finished_at_not_purged", table_name="jobs")
    op.drop_column("jobs", "files_purged_at")
