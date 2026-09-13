"""Scope category names by category type."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "20260913_0004"
down_revision: str | None = "20260913_0003"
branch_labels: str | Sequence[str] | None = None

_TABLE = "ledger_categories"
_NEW_NAME = "uq_ledger_categories_owner_parent_name_type"
_INDEX_NAME = "uq_ledger_categories_owner_parent_name_type_root"
_COLUMNS = ["owner_id", "parent_id", "name", "category_type"]
_OLD_COLUMNS = ["owner_id", "parent_id", "name"]


def upgrade() -> None:
    if context.is_offline_mode():
        op.drop_constraint(
            "ledger_categories_owner_id_parent_id_name_key", _TABLE, type_="unique"
        )
        op.create_unique_constraint(_NEW_NAME, _TABLE, _COLUMNS)
        op.create_index(
            _INDEX_NAME,
            _TABLE,
            _COLUMNS,
            unique=True,
            postgresql_nulls_not_distinct=True,
        )
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    constraints = inspector.get_unique_constraints(_TABLE)
    has_new_constraint = any(
        set(item.get("column_names", [])) == set(_COLUMNS) for item in constraints
    )
    if not has_new_constraint:
        old = next(
            (
                item
                for item in constraints
                if set(item.get("column_names", [])) == set(_OLD_COLUMNS)
            ),
            None,
        )
        if old is None or not old.get("name"):
            raise RuntimeError(
                "The existing category uniqueness constraint was not found"
            )
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(_TABLE) as batch:
                batch.drop_constraint(old["name"], type_="unique")
                batch.create_unique_constraint(_NEW_NAME, _COLUMNS)
        else:
            op.drop_constraint(old["name"], _TABLE, type_="unique")
            op.create_unique_constraint(_NEW_NAME, _TABLE, _COLUMNS)

    if _INDEX_NAME not in {item.get("name") for item in inspector.get_indexes(_TABLE)}:
        op.create_index(
            _INDEX_NAME,
            _TABLE,
            _COLUMNS,
            unique=True,
            postgresql_nulls_not_distinct=True,
        )


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_index(_INDEX_NAME, table_name=_TABLE)
        op.drop_constraint(_NEW_NAME, _TABLE, type_="unique")
        op.create_unique_constraint(
            "ledger_categories_owner_id_parent_id_name_key", _TABLE, _OLD_COLUMNS
        )
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _INDEX_NAME in {item.get("name") for item in inspector.get_indexes(_TABLE)}:
        op.drop_index(_INDEX_NAME, table_name=_TABLE)
    constraints = inspector.get_unique_constraints(_TABLE)
    current = next(
        (
            item
            for item in constraints
            if set(item.get("column_names", [])) == set(_COLUMNS)
        ),
        None,
    )
    if current is None or not current.get("name"):
        return
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(_TABLE) as batch:
            batch.drop_constraint(current["name"], type_="unique")
            batch.create_unique_constraint(
                "ledger_categories_owner_id_parent_id_name_key", _OLD_COLUMNS
            )
    else:
        op.drop_constraint(current["name"], _TABLE, type_="unique")
        op.create_unique_constraint(
            "ledger_categories_owner_id_parent_id_name_key", _TABLE, _OLD_COLUMNS
        )
