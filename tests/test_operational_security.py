import asyncio

import httpx
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import PlainTextResponse

from app.core.rate_limit import AuthRateLimitMiddleware
from app.main import app


def test_cors_and_auth_rate_limit_middleware_are_configured() -> None:
    middleware_classes = {middleware.cls for middleware in app.user_middleware}
    assert CORSMiddleware in middleware_classes
    assert AuthRateLimitMiddleware in middleware_classes


def test_auth_rate_limit_returns_stable_error() -> None:
    async def downstream(scope, receive, send):
        response = PlainTextResponse("ok")
        await response(scope, receive, send)

    limited = AuthRateLimitMiddleware(downstream, limit=1)

    async def exercise() -> None:
        transport = httpx.ASGITransport(app=limited)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            assert (await client.get("/api/v1/auth/google/login")).status_code == 200
            response = await client.get("/api/v1/auth/google/login")
            assert response.status_code == 429
            assert response.json()["detail"]["code"] == "RATE_LIMITED"

    asyncio.run(exercise())
