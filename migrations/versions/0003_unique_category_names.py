"""one category name per owner and parent

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-29

A plain UNIQUE (chat_id, parent_id, name) would not hold here: Postgres treats
NULLs as distinct, so two top-level rows -- both with parent_id NULL -- would
not collide, which is exactly the case that happens most. Coalescing to a
sentinel gives every row a comparable key, and lower(name) makes the rule match
what the user sees in a list of buttons.
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_categories_owner_parent_name"


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="categories")
