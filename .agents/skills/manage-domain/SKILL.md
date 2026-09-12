---
name: manage-domain
description: Define entities and business rules inside a feature domain without leaking HTTP or infrastructure concerns.
---

# Manage Domain

Use this skill when changing a feature's business concepts, invariants, or entity behavior.

- Put domain code in `app/features/<feature>/domain/`.
- Keep domain code independent from FastAPI routers, HTTP status codes, request/response schemas, and other feature presentations.
- Put rules that must hold regardless of caller in the domain layer or the feature application service.
- Keep use-case orchestration, queries, and transaction handling in `application/`, not in the domain entity.
- Reuse the project's SQLAlchemy model approach for simple features; introduce separate persistence mappings only when domain/persistence complexity justifies it.
- Expose domain failures as domain exceptions or values; translate them to HTTP responses in presentation.
- Add focused tests for each invariant and preserve the existing API contract unless a change is intentional.
