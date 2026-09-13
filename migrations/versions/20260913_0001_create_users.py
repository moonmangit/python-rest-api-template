"""Create the users table.

Revision ID: 20260913_0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260913_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None


def upgrade() -> None:
    # A database created by the pre-Alembic startup path may already have users.
    if not context.is_offline_mode() and sa.inspect(op.get_bind()).has_table("users"):
        return

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_index("ix_users_email", table_name="users")
        op.drop_table("users")
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return

    indexes = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_email" in indexes:
        op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
