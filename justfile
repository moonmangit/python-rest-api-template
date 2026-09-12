compose := "docker compose -f compose.yaml"

# Start PostgreSQL in the background.
setup:
    {{compose}} up -d

# Stop and remove the PostgreSQL container, preserving its data volume.
setdown:
    {{compose}} down

# Reset PostgreSQL and remove all containers, volumes, and orphans.
clean:
    {{compose}} down --volumes --remove-orphans

# Start the FastAPI development server with reload enabled.
dev:
    uv run python main.py

# Run the test suite.
test:
    uv run python -m pytest

# Check formatting and lint rules.
lint:
    uv run ruff check .
    uv run ruff format --check .

# Format Python source files.
format:
    uv run ruff format .

# Run the complete local quality gate.
check: lint test
