from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from random import choice, randint
from uuid import uuid4

from locust import HttpUser, between, task

SUPPLIER_CODES = ("SUP01", "SUP02", "SUP03")
OFFICE_CODES = ("MAD01", "MAD02", "BCN01", "BCN02", "VAL01", "SVQ01")
VEHICLES = (
    ("VH001", "Corolla", "Economy"),
    ("VH002", "Civic", "Economy"),
    ("VH003", "Qashqai", "SUV"),
    ("VH004", "Model 3", "Electric"),
)


def _build_total_amount() -> str:
    amount = Decimal(randint(5000, 50000)) / Decimal("100")
    return f"{amount:.2f}"


def _build_reservation_payload() -> dict[str, object]:
    pickup_datetime = datetime.now(UTC) + timedelta(days=7, minutes=randint(0, 14 * 24 * 60))
    dropoff_datetime = pickup_datetime + timedelta(days=randint(1, 10))
    pickup_office_code = choice(OFFICE_CODES)
    dropoff_candidates = tuple(code for code in OFFICE_CODES if code != pickup_office_code)
    dropoff_office_code = choice(dropoff_candidates)
    vehicle_code, model, category = choice(VEHICLES)
    customer_token = uuid4().hex[:12]

    return {
        "supplier_code": choice(SUPPLIER_CODES),
        "pickup_office_code": pickup_office_code,
        "dropoff_office_code": dropoff_office_code,
        "pickup_datetime": pickup_datetime.isoformat(),
        "dropoff_datetime": dropoff_datetime.isoformat(),
        "total_amount": _build_total_amount(),
        "customer": {
            "first_name": "Load",
            "last_name": "Test",
            "email": f"load.{customer_token}@example.com",
            "phone": f"+34123{randint(100000, 999999)}",
        },
        "vehicle": {
            "vehicle_code": vehicle_code,
            "model": model,
            "category": category,
        },
    }


class ReservationsApiUser(HttpUser):
    wait_time = between(0.05, 0.20)

    @task(1)
    def health(self) -> None:
        self.client.get("/api/v1/health", name="GET /api/v1/health")

    @task(9)
    def create_reservation(self) -> None:
        payload = _build_reservation_payload()
        with self.client.post(
            "/api/v1/reservations",
            json=payload,
            catch_response=True,
            name="POST /api/v1/reservations",
        ) as response:
            if response.status_code == 201:
                response.success()
                return
            response.failure(
                f"Unexpected status={response.status_code} body={response.text[:180]}"
            )
