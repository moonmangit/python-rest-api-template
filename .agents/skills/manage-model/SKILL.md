---
name: manage-model
description: Create and modify SQLAlchemy models following this project's database model conventions.
---

# Manage Models

Use this skill when adding or changing a database entity.

- Create one model per entity at `app/features/<feature>/domain/model.py`.
- Import `Base` from `app.core.database`.
- Use SQLAlchemy 2.x typed declarations: `Mapped[...]` and `mapped_column(...)`.
- Use a plural snake_case `__tablename__` and explicit constraints for required, unique, indexed, and length-limited fields.
- Keep relationships and foreign keys in the model that owns the database invariant.
- Keep connection, session, commit, and query code out of model classes.
- Keep HTTP types, request schemas, response schemas, and FastAPI imports out of the domain package.
- Import the model before `Base.metadata.create_all()` runs so metadata includes its table.
- Add or update Pydantic response/request schemas in the feature's `presentation/` package when the model changes.
- Update matching Bruno requests when model changes affect request or response JSON.
- Remember that startup table creation does not alter existing tables; never drop or silently rewrite existing data to apply a model change.

Verify with Python compilation, application import, and a database-backed smoke test when PostgreSQL is available.
