---
name: manage-api
description: Add and modify versioned FastAPI routes using this project's dependency, schema, and registration conventions.
---

# Manage API

Use this skill for HTTP endpoints, request validation, response schemas, and router wiring.

- Put resource routes in `app/features/<feature>/presentation/router.py`.
- Define an `APIRouter` with a resource prefix and tags, then include the feature router aggregate from `app/main.py` with the `/api/v1` prefix.
- Inject database access with `app.shared.dependencies.SessionDep`.
- Keep reusable Pydantic models in the feature's `presentation/schemas.py`.
- Use `ConfigDict(from_attributes=True)` when returning SQLAlchemy ORM instances.
- Keep HTTP concerns in the presentation router; move reusable domain/database logic to the feature's `application/` layer when it becomes non-trivial.
- Keep the presentation layer free of direct SQLAlchemy queries and transaction management; call an application use case instead.
- Do not add business rules to request schemas or route handlers merely because the feature is small.
- Preserve explicit status codes and useful conflict/not-found responses.
- Avoid changing trailing-slash behavior or public paths without a concrete compatibility reason.
- For every new or changed route, create or update a matching native Bruno `.bru` request under root-level `bruno/`.
- Add liveness/readiness behavior to the health routes rather than hiding database failures in generic responses.

Verify the generated OpenAPI paths and run a focused request smoke test against the local database when available.
