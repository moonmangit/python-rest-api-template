---
name: project-conventions
description: Apply the project structure and workflow conventions before changing this FastAPI application.
---

# Project Conventions

Use this skill for every change in this project.

## Structure

- Application code belongs under `app/`.
- Use `app/main.py` for FastAPI initialization and router registration.
- Use `app/core/` for configuration and database infrastructure shared by all features.
- Use `app/shared/` for cross-feature dependencies and operational endpoints.
- Use `app/features/<feature>/` as the bounded-context boundary.
- Every business feature MUST contain `domain/`, `application/`, and `presentation/` packages, even for a small first use case.
- Put SQLAlchemy entities in `app/features/<feature>/domain/`.
- Put use cases and persistence operations in `app/features/<feature>/application/`.
- Put HTTP routers and feature-specific schemas in `app/features/<feature>/presentation/`.
- Let application startup create missing local tables with `Base.metadata.create_all()`.
- Use `tests/` for focused unit and API contract tests.
- Keep local environment documentation in `.env.example` and project usage in `README.md`.
- Keep repository-wide quality automation in `.github/workflows/`.
- Keep package `__init__.py` files empty unless an explicit export is useful.
- Keep the root `main.py` launcher working because `just dev` runs `uv run python main.py`.

## API And Database

- Use SQLAlchemy 2.x typed mappings with `Mapped` and `mapped_column`.
- Get sessions through `app.core.database.get_db`; never create a new engine inside a route or service.
- Keep domain rules out of FastAPI routers and shared infrastructure.
- Enforce the dependency direction `presentation -> application -> domain`.
- Do not import FastAPI from `domain/` or `application/`.
- Do not put database queries, commits, or business rules in `presentation/`.
- Do not import one feature's internals directly into another feature.
- Register the feature router aggregate in `app/main.py` under `/api/v1`.
- Preserve the `DATABASE_URL` environment override and the local Compose default.
- Remember that `create_all()` does not alter existing tables; flag schema changes that need a future migration system.
- Do not perform destructive schema changes implicitly.

## Bruno

- Every API endpoint added or changed must have a matching request under root-level `bruno/` in the same change.
- Use `bruno/environments/local.bru` and `{{baseUrl}}` rather than hard-coded hosts in request files.
- Keep Bruno folders aligned with API resources and include representative JSON bodies for write requests.

## Verification

- Run focused Python compilation/import checks for changed modules.
- Validate the Compose file when database configuration changes.
- Check that the Bruno collection still covers the application OpenAPI paths.
- Run `just test` and `just lint` before completing behavior changes.
- Prefer `just check` as the complete local quality gate.
- Keep changes minimal and do not add new infrastructure without a concrete requirement.
