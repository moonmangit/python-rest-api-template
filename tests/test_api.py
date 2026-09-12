from app.main import app


def test_openapi_contains_current_api() -> None:
    paths = app.openapi()["paths"]

    assert "/" in paths
    assert "/api/v1/users/" in paths
    assert "/health/live" in paths
    assert "/health/ready" in paths
