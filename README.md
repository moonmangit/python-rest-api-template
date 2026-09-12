# Todo API

A FastAPI todo service using PostgreSQL, SQLAlchemy, JWT cookies, and role-based
authorization.

## Architecture

The application is organized by domain rather than by technical layer:

```text
app/
├── core/       # Configuration and database infrastructure
├── shared/     # Cross-feature dependencies and health checks
└── features/
    ├── auth/
    │   ├── domain/        # Authentication domain boundary
    │   ├── application/   # Authentication use cases
    │   └── presentation/  # Authentication router and dependencies
    ├── user/
    │   ├── domain/        # User entity and persistence model
    │   ├── application/   # User use cases
    │   └── presentation/  # HTTP router and schemas
    └── todo/
        ├── domain/        # Todo entity and persistence model
        ├── application/   # Todo use cases and ownership rules
        └── presentation/  # HTTP routers and schemas
```

New business capabilities belong under `app/features/<feature>/`. Keep each
feature's domain rules, application operations, and HTTP boundary together.

## Layer Responsibilities

Every business feature uses the same three internal boundaries. These boundaries
are required even when a feature starts with only one endpoint.

### Domain

The domain describes what the business concept is and which rules belong to it.

For the users feature:

```text
app/features/user/domain/model.py
```

The `User` entity lives here. Domain code must not know about HTTP requests,
HTTP status codes, FastAPI routers, or another feature's presentation layer.
Rules that must always be true belong here or in the feature application service.
This starter keeps the SQLAlchemy mapping with the entity to stay small; it is
DDD-inspired rather than strict Clean Architecture. If persistence becomes
complex or needs multiple implementations, add an infrastructure adapter and
ports at that point.

### Application

The application layer describes what the system does for a use case. It
coordinates the domain entity, database session, queries, transactions, and
domain errors.

For the users feature:

```text
app/features/user/application/service.py
```

`create_user()` is an application use case. It normalizes the email, checks for
duplicates, creates the entity, commits it, and returns the result. It does not
know whether the caller is HTTP, a background job, or a test.

### Presentation

The presentation layer adapts the application to an external interface. In
this project that interface is FastAPI.

For the users feature:

```text
app/features/user/presentation/router.py
app/features/user/presentation/schemas.py
```

The router owns URLs, dependency injection, request validation, response models,
and HTTP error translation. It must call an application use case instead of
containing database queries or business workflows.

## Dependency Direction

The normal request direction is:

```text
HTTP request
    -> presentation
    -> application
    -> domain
    -> shared/core infrastructure
    -> HTTP response
```

Presentation may depend on application. Application may depend on domain and
shared/core infrastructure. Domain must not depend on presentation. Features
must not reach into another feature's internal modules.

## Where Code Belongs

| Question | Location |
| --- | --- |
| What URL or HTTP status should this use? | Feature `presentation/` |
| How should a request body be validated? | Feature `presentation/schemas.py` |
| What operation should the system perform? | Feature `application/` |
| What rule must hold for the business entity? | Feature `domain/` |
| How is a SQLAlchemy session created? | `app/core/database.py` |
| Is this shared by multiple features? | `app/core/` or `app/shared/` |
| Is this public API behavior? | Also update root-level `bruno/` |

## Create A New Feature

Start with this shape:

```text
app/features/orders/
├── __init__.py
├── application/
│   ├── __init__.py
│   └── service.py
├── domain/
│   ├── __init__.py
│   └── model.py
└── presentation/
    ├── __init__.py
    ├── router.py
    └── schemas.py
```

Then register its router in `app/features/router.py`, add focused tests, and
add matching Bruno requests under `bruno/orders/`.

Do not add repositories, ports, events, or extra abstractions only to fill the
folders. Add them when the domain or a second implementation requires them.

## Requirements

- Python 3.10+
- uv
- Docker Compose
- just

## Development

```bash
uv sync
just setup
just dev
```

The API runs at `http://127.0.0.1:3001`.

## Commands

| Command | Purpose |
| --- | --- |
| `just setup` | Start PostgreSQL |
| `just setdown` | Stop PostgreSQL and preserve data |
| `just clean` | Remove PostgreSQL containers and volumes |
| `just dev` | Start the reload-enabled API server |
| `just test` | Run tests |
| `just lint` | Run Ruff checks |
| `just format` | Format Python files |
| `just check` | Run linting, formatting, and tests |

## API

- `GET /health/live` checks that the process is running.
- `GET /health/ready` checks PostgreSQL connectivity.
- `POST /api/v1/auth/register` registers a user without authentication. The
  first registered user becomes an administrator automatically; later users
  are normal users.
- `POST /api/v1/auth/login` authenticates and sets the HttpOnly JWT cookie.
- `GET /api/v1/auth/me` returns the current user.
- `POST /api/v1/auth/logout` clears the authentication cookie.
- `DELETE /api/v1/auth/me` deletes the current account and owned todos.
- `GET/POST /api/v1/users/` and `GET/PATCH/DELETE /api/v1/users/{id}` provide
  admin-only user management.
- `GET/POST /api/v1/todos/` and `GET/PATCH/DELETE /api/v1/todos/{id}` provide
  authenticated users' own todo CRUD.
- `GET/POST /api/v1/admin/todos/` and `GET/PATCH/DELETE
  /api/v1/admin/todos/{id}` provide admin todo management across users.
- `GET /docs` opens the development OpenAPI UI.

Copy `.env.example` to `.env` when local configuration overrides are needed.
Setting `ADMIN_USERNAME` and `ADMIN_PASSWORD` bootstraps an administrator on
startup. Missing tables are created automatically when the application starts.
The existing starter schema predates the todo/auth tables and `create_all()` does
not alter existing tables; use a migration or reset the local database before
running against an old development database.

Run `just check` before opening a pull request. CI runs the same quality checks
with the locked uv dependencies.
