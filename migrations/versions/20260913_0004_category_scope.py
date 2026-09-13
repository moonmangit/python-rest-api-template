"""Scope category names by category type."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260913_0004"
down_revision: str | None = "20260913_0003"
branch_labels: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ledger_categories_owner_id_parent_id_name_key",
        "ledger_categories",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_ledger_categories_owner_parent_name_type",
        "ledger_categories",
        ["owner_id", "parent_id", "name", "category_type"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_ledger_categories_owner_parent_name_type",
        "ledger_categories",
        type_="unique",
    )
    op.create_unique_constraint(
        "ledger_categories_owner_id_parent_id_name_key",
        "ledger_categories",
        ["owner_id", "parent_id", "name"],
    )
