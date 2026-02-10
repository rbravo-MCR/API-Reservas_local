from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from reservas_api.api.middleware import (
    ErrorHandlerMiddleware,
    HTTPSEnforcerMiddleware,
    RateLimiterMiddleware,
    validation_exception_handler,
)
from reservas_api.api.routers.health import router as health_router
from reservas_api.api.routers.reservations import router as reservations_router
from reservas_api.shared.config import ApplicationContainer, settings


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    container = ApplicationContainer(settings)

    @asynccontextmanager
    async def app_lifespan(app: FastAPI):
        """Initialize and release shared app resources."""
        app.state.container = container
        app.state.session_factory = container.session_factory
        app.state.create_reservation_use_case_factory = container.create_create_reservation_use_case
        await container.startup()
        try:
            yield
        finally:
            await container.shutdown()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
        version=settings.app_version,
        lifespan=app_lifespan,
    )
    if settings.cors_allowed_origins_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.add_middleware(
        RateLimiterMiddleware,
        default_limit_per_minute=settings.rate_limit_requests_per_minute,
        reservations_limit_per_minute=settings.rate_limit_reservations_per_minute,
    )
    app.add_middleware(
        HTTPSEnforcerMiddleware,
        force_https=settings.force_https,
    )
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(reservations_router, prefix="/api/v1")
    return app
