import asyncio
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from time import monotonic

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from reservas_api.api.schemas import ErrorResponseDTO


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Apply in-memory per-IP/per-endpoint request limits."""

    def __init__(  # type: ignore[no-untyped-def]
        self,
        app,
        *,
        default_limit_per_minute: int = 120,
        reservations_limit_per_minute: int = 30,
    ) -> None:
        super().__init__(app)
        if default_limit_per_minute <= 0:
            raise ValueError("default_limit_per_minute must be greater than zero")
        if reservations_limit_per_minute <= 0:
            raise ValueError("reservations_limit_per_minute must be greater than zero")
        self._default_limit = default_limit_per_minute
        self._reservations_limit = reservations_limit_per_minute
        self._request_windows: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Reject requests with HTTP 429 when the configured window is exceeded."""
        limit = self._resolve_limit(request)
        key = self._build_key(request)
        now = monotonic()
        cutoff = now - 60.0

        async with self._lock:
            window = self._request_windows[key]
            while window and window[0] <= cutoff:
                window.popleft()
            if len(window) >= limit:
                return JSONResponse(
                    status_code=429,
                    content=ErrorResponseDTO(
                        error="Too many requests",
                        message="Rate limit exceeded. Please retry later.",
                        code="RATE_LIMIT_EXCEEDED",
                    ).model_dump(),
                )
            window.append(now)

        return await call_next(request)

    def _resolve_limit(self, request: Request) -> int:
        is_reservations_write = (
            request.method.upper() == "POST"
            and request.url.path.rstrip("/") == "/api/v1/reservations"
        )
        return self._reservations_limit if is_reservations_write else self._default_limit

    @staticmethod
    def _build_key(request: Request) -> str:
        client_ip = request.client.host if request.client is not None else "unknown"
        return f"{client_ip}:{request.method.upper()}:{request.url.path}"
