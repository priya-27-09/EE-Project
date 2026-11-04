"""
AI Civic Guardian — In-Memory Rate Limiting & Abuse Protection
Provides thread-safe sliding-window rate limiting for sensitive endpoints
such as authentication, registration, and file uploads without external dependencies.
"""

import time
import threading
from typing import Dict, List, Tuple, Optional
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class SlidingWindowRateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        # Storage: key -> list of float timestamps
        self._records: Dict[str, List[float]] = {}
        # Route specific limits: prefix -> (max_requests, window_seconds)
        self.route_limits: Dict[str, Tuple[int, int]] = {
            "/auth/login": (25, 60),       # 25 attempts / min
            "/auth/register": (60, 60),    # 60 registrations / min
        }
        # Global fallback for any protected sensitive routes
        self.default_limit: Tuple[int, int] = (120, 60)  # 120 req / min
        self._enabled: bool = True

    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool):
        with self._lock:
            self._enabled = enabled

    def clear(self):
        """Reset all rate limiter records (useful for test isolation)."""
        with self._lock:
            self._records.clear()

    def get_limit_for_path(self, path: str) -> Optional[Tuple[int, int]]:
        for prefix, limit in self.route_limits.items():
            if path == prefix or path.startswith(prefix + "/"):
                return limit
        return None

    def check_rate_limit(self, client_ip: str, path: str) -> Tuple[bool, int]:
        """
        Check if request exceeds rate limit.
        Returns: (is_allowed, retry_after_seconds)
        """
        if not self._enabled:
            return True, 0

        limit = self.get_limit_for_path(path)
        if not limit:
            return True, 0

        max_requests, window_seconds = limit
        now = time.time()
        key = f"{client_ip}:{path}"

        with self._lock:
            timestamps = self._records.get(key, [])
            # Purge timestamps outside sliding window
            cutoff = now - window_seconds
            timestamps = [ts for ts in timestamps if ts > cutoff]

            if len(timestamps) >= max_requests:
                # Calculate retry after
                earliest = timestamps[0]
                retry_after = max(1, int(earliest + window_seconds - now))
                self._records[key] = timestamps
                return False, retry_after

            timestamps.append(now)
            self._records[key] = timestamps
            return True, 0


# Global singleton instance
limiter = SlidingWindowRateLimiter()


class SecurityHeadersAndRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract client IP
        client_ip = request.client.host if request.client else "127.0.0.1"
        path = request.url.path

        # Check rate limit on sensitive routes
        if request.method in ["POST", "PUT", "PATCH"]:
            allowed, retry_after = limiter.check_rate_limit(client_ip, path)
            if not allowed:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Rate limit exceeded. Please try again later.",
                        "error": "TOO_MANY_REQUESTS",
                        "retry_after": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )

        response = await call_next(request)

        # Inject standard security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response
