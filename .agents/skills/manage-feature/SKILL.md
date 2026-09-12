---
name: manage-feature
description: Create and evolve a bounded feature using this project's domain-driven structure.
---

# Manage Features

Use this skill when adding a new business capability or bounded context.

- Create the feature at `app/features/<feature>/`.
- ALWAYS create `domain/`, `application/`, and `presentation/` packages with `__init__.py` files, even when one layer initially has little code.
- Keep `domain/` for entities and domain rules only.
- Keep `application/` for use cases and orchestration only.
- Keep `presentation/` for HTTP routers, request schemas, response schemas, and HTTP error translation only.
- Add the feature router to `app/features/router.py`; keep `app/main.py` as the composition root.
- Keep feature internals independent from other feature internals. Share only stable infrastructure through `app/core/` or `app/shared/`.
- Enforce the dependency direction `presentation -> application -> domain`; the domain must not import presentation code.
- Do not place a route, Pydantic HTTP schema, SQLAlchemy query, or transaction in the wrong layer to avoid creating a file.
- Add focused tests under `tests/` and Bruno requests under `bruno/<feature>/` for public endpoints.
- Do not create repositories, interfaces, events, or extra layers until a concrete second implementation or domain need justifies them.
- Preserve existing URL prefixes and response contracts unless the feature explicitly changes the API.

Verify imports, OpenAPI paths, tests, linting, and the local database startup path.
