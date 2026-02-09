from fastapi import FastAPI
from fastapi.testclient import TestClient

from reservas_api.api.middleware import HTTPSEnforcerMiddleware, RateLimiterMiddleware


def test_https_enforcer_redirects_http_requests_when_enabled() -> None:
    app = FastAPI()
    app.add_middleware(HTTPSEnforcerMiddleware, force_https=True)

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    response = client.get("/ping", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"].startswith("https://")


def test_https_enforcer_adds_hsts_header_when_request_is_secure() -> None:
    app = FastAPI()
    app.add_middleware(HTTPSEnforcerMiddleware, force_https=True)

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    response = client.get("/ping", headers={"x-forwarded-proto": "https"})

    assert response.status_code == 200
    assert response.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"


def test_rate_limiter_limits_requests_per_ip_and_endpoint() -> None:
    app = FastAPI()
    app.add_middleware(
        RateLimiterMiddleware,
        default_limit_per_minute=20,
        reservations_limit_per_minute=2,
    )

    @app.post("/api/v1/reservations")
    async def create_reservation() -> dict[str, str]:
        return {"status": "created"}

    client = TestClient(app)
    first = client.post("/api/v1/reservations")
    second = client.post("/api/v1/reservations")
    third = client.post("/api/v1/reservations")

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.json()["code"] == "RATE_LIMIT_EXCEEDED"
