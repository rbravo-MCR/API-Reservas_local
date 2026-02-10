from fastapi.middleware.cors import CORSMiddleware

from reservas_api.api import app as app_module


def test_create_app_registers_health_and_reservations_routes() -> None:
    application = app_module.create_app()
    route_paths = {route.path for route in application.routes}

    assert "/api/v1/health" in route_paths
    assert "/api/v1/reservations" in route_paths


def test_create_app_enables_cors_middleware_when_origins_are_configured(monkeypatch) -> None:
    monkeypatch.setattr(
        app_module.settings,
        "cors_allowed_origins",
        "http://localhost:3000,http://localhost:5173",
    )

    application = app_module.create_app()
    middleware_types = {middleware.cls for middleware in application.user_middleware}

    assert CORSMiddleware in middleware_types
