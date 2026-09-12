---
name: manage-service
description: Add reusable domain and persistence operations without coupling business logic to FastAPI routes.
---

# Manage Services

Use this skill when an operation has enough domain logic to be reused or when a route would otherwise become difficult to read.

- Create use-case services at `app/features/<feature>/application/service.py`; do not create the layer for a one-line pass-through.
- Accept a SQLAlchemy `Session` from the caller rather than creating an engine or session internally.
- Keep FastAPI decorators, `Depends`, HTTP status codes, and request parsing in the feature's `presentation/` layer.
- Keep queries, domain rules, entity creation, and transaction behavior in the service layer.
- Keep the service in the feature's `application/` package and keep it independent from FastAPI request/response types.
- Enforce domain invariants in the service as well as at the HTTP validation boundary.
- Return ORM entities or simple domain values; let the API layer serialize them.
- Make transaction ownership explicit. Follow the existing route behavior unless the service is the clear owner of the complete operation.
- Translate service/domain failures to HTTP errors in the feature's presentation router.
- Add focused tests or smoke checks for duplicate, missing, and successful paths when behavior changes.
- Update the corresponding Bruno request whenever a service change alters an endpoint's observable behavior.
