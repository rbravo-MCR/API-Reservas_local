from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from reservas_api.api.routers.reservations import get_create_reservation_use_case
from reservas_api.application import CreateReservationRequest
from reservas_api.domain.entities import Reservation
from reservas_api.domain.value_objects import ReservationCode
from reservas_api.main import app


class FakeCreateReservationUseCase:
    def __init__(self) -> None:
        self.calls = 0
        self.last_request: CreateReservationRequest | None = None

    async def execute(self, request: CreateReservationRequest) -> Reservation:
        self.calls += 1
        self.last_request = request
        return Reservation(
            id=1,
            reservation_code=ReservationCode("APIX1234"),
            supplier_code=request.supplier_code,
            pickup_office_code=request.pickup_office_code,
            dropoff_office_code=request.dropoff_office_code,
            pickup_datetime=request.pickup_datetime,
            dropoff_datetime=request.dropoff_datetime,
            total_amount=request.total_amount,
            customer_snapshot=request.customer,
            vehicle_snapshot=request.vehicle,
            created_at=datetime.now(UTC),
        )


@pytest.fixture
def reservations_client():
    fake_use_case = FakeCreateReservationUseCase()
    app.dependency_overrides[get_create_reservation_use_case] = lambda: fake_use_case
    client = TestClient(app)
    try:
        yield client, fake_use_case
    finally:
        app.dependency_overrides.clear()


def _valid_payload() -> dict:
    pickup = datetime(2026, 12, 1, 10, 0, tzinfo=UTC)
    dropoff = pickup + timedelta(days=2)
    return {
        "supplier_code": "SUP01",
        "pickup_office_code": "OFF001",
        "dropoff_office_code": "OFF002",
        "pickup_datetime": pickup.isoformat(),
        "dropoff_datetime": dropoff.isoformat(),
        "total_amount": "180.50",
        "customer": {
            "first_name": "Ana",
            "last_name": "Perez",
            "email": "ana@example.com",
            "phone": "+34123456789",
        },
        "vehicle": {
            "vehicle_code": "VH001",
            "model": "Corolla",
            "category": "Economy",
        },
    }


def test_post_reservations_with_valid_data_returns_created(reservations_client) -> None:
    client, fake_use_case = reservations_client
    response = client.post("/api/v1/reservations", json=_valid_payload())

    assert response.status_code == 201
    payload = response.json()
    assert payload["reservation_code"] == "APIX1234"
    assert payload["status"] == "CREATED"
    assert payload["supplier_code"] == "SUP01"
    assert fake_use_case.calls == 1


def test_post_reservations_missing_required_fields_returns_422(reservations_client) -> None:
    client, fake_use_case = reservations_client
    payload = _valid_payload()
    payload.pop("customer")

    response = client.post("/api/v1/reservations", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "Validation error"
    assert body["code"] == "VALIDATION_ERROR"
    assert fake_use_case.calls == 0


def test_post_reservations_invalid_data_types_returns_422(reservations_client) -> None:
    client, fake_use_case = reservations_client
    payload = _valid_payload()
    payload["total_amount"] = "not-a-number"

    response = client.post("/api/v1/reservations", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "Validation error"
    assert body["code"] == "VALIDATION_ERROR"
    assert fake_use_case.calls == 0


def test_post_reservations_returns_http_201(reservations_client) -> None:
    client, _ = reservations_client
    response = client.post("/api/v1/reservations", json=_valid_payload())

    assert response.status_code == 201
    assert Decimal(response.json()["total_amount"]) == Decimal("180.50")
