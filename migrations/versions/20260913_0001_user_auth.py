"""Add Google identity and roles to users.

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
    if context.is_offline_mode():
        _create_users_table()
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("google_subject", sa.String(length=255), nullable=True),
            sa.Column(
                "role", sa.String(length=5), nullable=False, server_default="user"
            ),
            sa.UniqueConstraint("email"),
            sa.UniqueConstraint("google_subject"),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=False)
        op.create_index(
            "ix_users_google_subject", "users", ["google_subject"], unique=False
        )
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "google_subject" not in columns:
        op.add_column(
            "users", sa.Column("google_subject", sa.String(255), nullable=True)
        )
        op.create_index(
            "ix_users_google_subject", "users", ["google_subject"], unique=True
        )
    if "role" not in columns:
        op.add_column(
            "users",
            sa.Column("role", sa.String(5), nullable=True, server_default="user"),
        )
        op.execute("UPDATE users SET role = 'user' WHERE role IS NULL")
        op.execute(
            "UPDATE users SET role = 'admin' WHERE id = (SELECT MIN(id) FROM users)"
        )
        op.alter_column("users", "role", nullable=False, server_default="user")


def _create_users_table() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("google_subject", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=5), nullable=False, server_default="user"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("google_subject"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_index(
        "ix_users_google_subject", "users", ["google_subject"], unique=False
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "role" in columns:
        op.drop_column("users", "role")
    if "google_subject" in columns:
        indexes = {index["name"] for index in inspector.get_indexes("users")}
        if "ix_users_google_subject" in indexes:
            op.drop_index("ix_users_google_subject", table_name="users")
        op.drop_column("users", "google_subject")
