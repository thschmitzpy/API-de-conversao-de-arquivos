from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_progress"
down_revision: Union[str, None] = "0002_files_purged_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("progress", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "progress")
