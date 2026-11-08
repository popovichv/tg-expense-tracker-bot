"""drop currency

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-07

Currency was a setting on the user and a code on every expense, and a report
could not add two of them together. One currency throughout is what the bot
assumes now, so both columns go.

The downgrade restores the shape of the schema but not the data. Every row
comes back as USD, because the code each expense was recorded in is dropped
here and nothing else holds it.
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("expenses", "currency")
    op.drop_column("users", "currency")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
    )
    op.add_column(
        "expenses",
        sa.Column("currency", sa.String(), nullable=False, server_default="USD"),
    )
