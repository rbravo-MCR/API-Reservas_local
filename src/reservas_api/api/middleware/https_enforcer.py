from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import RedirectResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware


class HTTPSEnforcerMiddleware(BaseHTTPMiddleware):
    """Redirect HTTP to HTTPS and add HSTS header when enabled."""

    def __init__(self, app, *, force_https: bool = False) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._force_https = force_https

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Apply HTTPS enforcement to incoming requests."""
        if self._force_https:
            forwarded_proto = request.headers.get("x-forwarded-proto", "")
            current_scheme = forwarded_proto or request.url.scheme
            if current_scheme.lower() != "https":
                https_url = request.url.replace(scheme="https")
                return RedirectResponse(url=str(https_url), status_code=307)

        response = await call_next(request)
        if self._force_https:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response
