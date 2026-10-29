"""created_at as timestamptz

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-29

"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "expenses",
        "created_at",
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        existing_server_default=sa.text("now()"),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        "expenses",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        existing_server_default=sa.text("now()"),
        existing_nullable=False,
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
