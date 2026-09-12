---
name: manage-testing
description: Add focused pytest coverage for API contracts, services, validation, and database behavior in this project.
---

# Manage Testing

Use this skill when behavior changes or when adding a new API resource.

- Put tests under `tests/` and use `test_*.py` names.
- Organize feature tests by bounded context, for example `tests/features/users/`, when the test suite grows beyond a few files.
- Keep unit tests isolated from the development PostgreSQL database; use an in-memory SQLite session for model/service behavior.
- Test successful paths, validation failures, duplicate/conflict behavior, and important API contract paths.
- Keep database fixtures request-scoped or function-scoped and always close sessions.
- Use the real PostgreSQL service for focused integration checks when dialect-specific behavior matters.
- Run `just check` and the nearest relevant smoke check before declaring the change complete.
