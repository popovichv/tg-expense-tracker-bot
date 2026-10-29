"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-28

Baseline of the schema that models/models.py defines. Constraint names are
spelled out via op.f() so they match the naming convention on Base.metadata.
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("chat_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("chat_id", name=op.f("pk_users")),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        # NULL chat_id marks a category shared with every user.
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["categories.id"],
            name=op.f("fk_categories_parent_id_categories"),
        ),
        sa.ForeignKeyConstraint(
            ["chat_id"],
            ["users.chat_id"],
            name=op.f("fk_categories_chat_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
    )
    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("spent_at", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["chat_id"], ["users.chat_id"], name=op.f("fk_expenses_chat_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_expenses_category_id_categories"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expenses")),
    )


def downgrade() -> None:
    op.drop_table("expenses")
    op.drop_table("categories")
    op.drop_table("users")
