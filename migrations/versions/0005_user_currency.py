"""per-user currency

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-29

The currency already stored on each expense is left untouched: it is the
record of what was spent, and changing the setting must not rewrite it. This
adds the setting that new expenses are recorded with.
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
    )


def downgrade() -> None:
    op.drop_column("users", "currency")
