---
name: manage-database
description: Configure and use the PostgreSQL and SQLAlchemy database layer for this project safely.
---

# Manage Database

Use this skill for database connectivity, sessions, tables, and local PostgreSQL operations.

- Keep the engine, `Base`, `SessionLocal`, and `get_db` in `app/core/database.py`.
- Keep environment-backed settings in `app/core/config.py`.
- Preserve the `DATABASE_URL` environment variable and default to the local Compose database: `postgresql+psycopg://app:app@localhost:5432/app`.
- Use the existing PostgreSQL service from `compose.yaml`; do not add a second database service.
- Start the database with `just setup`, stop it with `just setdown`, and reset it with `just clean`.
- Close every request-scoped session through the existing generator dependency.
- Use typed SQLAlchemy 2.x mappings and import feature models before metadata initialization.
- Initialize missing local tables through application startup with `Base.metadata.create_all()`.
- Remember that `create_all()` does not alter existing tables. Use `just clean` for a local reset only when data can be discarded, and flag schema changes that need a future migration system.
- Prefer focused database checks such as `SELECT 1`, table initialization, and the affected repository/service operation.
