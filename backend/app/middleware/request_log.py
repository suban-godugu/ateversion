from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger
from app.core.rate_limit import api_limiter, client_key

logger = get_logger("http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        start = time.perf_counter()

        # Skip rate limit for health probes
        path = request.url.path
        if not path.endswith(("/health", "/ready")) and path.startswith("/api"):
            try:
                api_limiter.check(client_key(request, "api"))
            except Exception as exc:
                from fastapi.responses import JSONResponse

                return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            status = getattr(response, "status_code", 500) if response else 500
            if response is not None:
                response.headers["X-Request-Id"] = request_id
            logger.info(
                "request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": path,
                    "status": status,
                    "duration_ms": duration_ms,
                },
            )
