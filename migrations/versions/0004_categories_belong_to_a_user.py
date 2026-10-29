"""categories always belong to a user

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-29

Shared categories, marked by a NULL chat_id, are replaced by per-user copies
seeded when a user registers, so every category has an owner who can rename or
delete it. Any shared rows are removed first; none were ever created, and the
foreign key from expenses refuses the delete if one is somehow in use.

The unique index loses its coalesce on chat_id, which is pointless once the
column cannot be NULL. parent_id keeps its own, since top-level rows still
have none.
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_categories_owner_parent_name"


def upgrade() -> None:
    op.execute("DELETE FROM categories WHERE chat_id IS NULL")
    op.alter_column(
        "categories",
        "chat_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.drop_index(INDEX_NAME, table_name="categories")
    op.create_index(
        INDEX_NAME,
        "categories",
        [
            sa.text("chat_id"),
            sa.text("coalesce(parent_id, 0)"),
            sa.text("lower(name)"),
        ],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="categories")
    op.create_index(
        INDEX_NAME,
        "categories",
        [
            sa.text("coalesce(chat_id, 0)"),
            sa.text("coalesce(parent_id, 0)"),
            sa.text("lower(name)"),
        ],
        unique=True,
    )
    op.alter_column(
        "categories",
        "chat_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
