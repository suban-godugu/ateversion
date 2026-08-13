from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request


class InMemoryRateLimiter:
    """Simple sliding-window limiter (per-process). Redis can replace later."""

    def __init__(self, *, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            q.append(now)


# Defaults: 120 req/min per IP for API; tighter for auth
api_limiter = InMemoryRateLimiter(limit=120, window_seconds=60)
auth_limiter = InMemoryRateLimiter(limit=20, window_seconds=60)
ws_limiter = InMemoryRateLimiter(limit=30, window_seconds=60)


def client_key(request: Request, suffix: str = "") -> str:
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    return f"{ip}:{suffix}" if suffix else ip
