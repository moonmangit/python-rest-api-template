"""Add account state, sessions, authorization, and spending ledger tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260913_0002"
down_revision: str | None = "20260913_0001"
branch_labels: str | Sequence[str] | None = None


def upgrade() -> None:
    if context.is_offline_mode():
        _upgrade_users()
        _create_tables()
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    _upgrade_users(inspector)
    _create_tables(inspector)


def _upgrade_users(inspector=None) -> None:
    columns = (
        {column["name"] for column in inspector.get_columns("users")}
        if inspector is not None
        else set()
    )
    if "status" not in columns:
        op.add_column(
            "users",
            sa.Column("status", sa.String(8), nullable=True, server_default="enabled"),
        )
        op.execute("UPDATE users SET status = 'enabled' WHERE status IS NULL")
        op.alter_column("users", "status", nullable=False, server_default="enabled")
    if "timezone" not in columns:
        op.add_column(
            "users",
            sa.Column("timezone", sa.String(64), nullable=True, server_default="UTC"),
        )
        op.execute("UPDATE users SET timezone = 'UTC' WHERE timezone IS NULL")
        op.alter_column("users", "timezone", nullable=False, server_default="UTC")
    if "default_currency" not in columns:
        op.add_column(
            "users",
            sa.Column(
                "default_currency", sa.String(3), nullable=True, server_default="USD"
            ),
        )
        op.execute(
            "UPDATE users SET default_currency = 'USD' WHERE default_currency IS NULL"
        )
        op.alter_column(
            "users", "default_currency", nullable=False, server_default="USD"
        )
    if inspector is None or "role" in columns:
        if inspector is None or inspector.bind.dialect.name == "postgresql":
            op.alter_column(
                "users",
                "role",
                type_=sa.String(6),
                existing_type=sa.String(5),
                existing_nullable=False,
            )
    op.execute("UPDATE users SET role = 'member' WHERE role = 'user'")
    if inspector is None or inspector.bind.dialect.name == "postgresql":
        op.alter_column("users", "role", server_default="member")


def _create_tables(inspector=None) -> None:
    existing = set(inspector.get_table_names()) if inspector is not None else set()
    if "refresh_sessions" not in existing:
        op.create_table(
            "refresh_sessions",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("replaced_by_id", sa.String(64), nullable=True),
            sa.Column("user_agent", sa.String(512), nullable=True),
            sa.Column("ip_address", sa.String(64), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["replaced_by_id"], ["refresh_sessions.id"], ondelete="SET NULL"
            ),
        )
        op.create_index("ix_refresh_sessions_user_id", "refresh_sessions", ["user_id"])
        op.create_index(
            "ix_refresh_sessions_token_hash",
            "refresh_sessions",
            ["token_hash"],
            unique=True,
        )

    if "audit_events" not in existing:
        op.create_table(
            "audit_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("target_user_id", sa.Integer(), nullable=True),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("entity_type", sa.String(100), nullable=False),
            sa.Column("entity_id", sa.String(100), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["actor_user_id"], ["users.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["target_user_id"], ["users.id"], ondelete="SET NULL"
            ),
        )
        op.create_index(
            "ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"]
        )
        op.create_index(
            "ix_audit_events_target_user_id", "audit_events", ["target_user_id"]
        )

    if "application_grants" not in existing:
        op.create_table(
            "application_grants",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("application", sa.String(100), nullable=False),
            sa.Column(
                "enabled", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("user_id", "application"),
        )
        op.create_index(
            "ix_application_grants_user_id", "application_grants", ["user_id"]
        )

    if "ledger_categories" not in existing:
        op.create_table(
            "ledger_categories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("parent_id", sa.Integer(), nullable=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("category_type", sa.String(7), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "archived", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["parent_id"], ["ledger_categories.id"], ondelete="CASCADE"
            ),
            sa.UniqueConstraint("owner_id", "parent_id", "name"),
        )
        op.create_index(
            "ix_ledger_categories_owner_id", "ledger_categories", ["owner_id"]
        )
        op.create_index(
            "ix_ledger_categories_parent_id", "ledger_categories", ["parent_id"]
        )

    if "ledger_records" not in existing:
        op.create_table(
            "ledger_records",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("record_type", sa.String(7), nullable=False),
            sa.Column("amount_minor", sa.Integer(), nullable=False),
            sa.Column("currency_code", sa.String(3), nullable=False),
            sa.Column("record_date", sa.Date(), nullable=False),
            sa.Column("category_id", sa.Integer(), nullable=False),
            sa.Column("subcategory_id", sa.Integer(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "amount_minor > 0", name="ck_ledger_records_positive_amount"
            ),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["category_id"], ["ledger_categories.id"]),
            sa.ForeignKeyConstraint(["subcategory_id"], ["ledger_categories.id"]),
        )
        op.create_index("ix_ledger_records_owner_id", "ledger_records", ["owner_id"])
        op.create_index(
            "ix_ledger_records_record_date", "ledger_records", ["record_date"]
        )
        op.create_index(
            "ix_ledger_records_category_id", "ledger_records", ["category_id"]
        )
        op.create_index(
            "ix_ledger_records_subcategory_id", "ledger_records", ["subcategory_id"]
        )

    if "ledger_attachments" not in existing:
        op.create_table(
            "ledger_attachments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("record_id", sa.Integer(), nullable=False),
            sa.Column("storage_key", sa.String(255), nullable=False),
            sa.Column("content_type", sa.String(100), nullable=False),
            sa.Column("byte_size", sa.Integer(), nullable=False),
            sa.Column("checksum", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["record_id"], ["ledger_records.id"], ondelete="CASCADE"
            ),
            sa.UniqueConstraint("storage_key"),
        )
        op.create_index(
            "ix_ledger_attachments_owner_id", "ledger_attachments", ["owner_id"]
        )
        op.create_index(
            "ix_ledger_attachments_record_id", "ledger_attachments", ["record_id"]
        )

    if "ledger_idempotency_keys" not in existing:
        op.create_table(
            "ledger_idempotency_keys",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(255), nullable=False),
            sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column("record_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["record_id"], ["ledger_records.id"], ondelete="CASCADE"
            ),
            sa.UniqueConstraint("owner_id", "key"),
        )
        op.create_index(
            "ix_ledger_idempotency_keys_owner_id",
            "ledger_idempotency_keys",
            ["owner_id"],
        )


def downgrade() -> None:
    op.drop_table("ledger_idempotency_keys")
    op.drop_table("ledger_attachments")
    op.drop_table("ledger_records")
    op.drop_table("ledger_categories")
    op.drop_table("application_grants")
    op.drop_table("audit_events")
    op.drop_table("refresh_sessions")
