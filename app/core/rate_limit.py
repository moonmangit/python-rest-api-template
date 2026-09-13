import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit: int, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path.startswith("/api/v1/auth/"):
            client = request.client.host if request.client else "unknown"
            now = time.monotonic()
            timestamps = self._requests[client]
            while timestamps and now - timestamps[0] >= self.window_seconds:
                timestamps.popleft()
            if len(timestamps) >= self.limit:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": {
                            "code": "RATE_LIMITED",
                            "message": "Too many authentication requests",
                        }
                    },
                    headers={"Retry-After": str(self.window_seconds)},
                )
            timestamps.append(now)
        return await call_next(request)
