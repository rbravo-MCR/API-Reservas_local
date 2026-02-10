from __future__ import annotations

import os
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
STRESS_RUN_ID = os.getenv("STRESS_RUN_ID", "default")


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
            "first_name": "Stress",
            "last_name": "Test",
            "email": f"stress.{STRESS_RUN_ID}.{customer_token}@example.com",
            "phone": f"+34123{randint(100000, 999999)}",
        },
        "vehicle": {
            "vehicle_code": vehicle_code,
            "model": model,
            "category": category,
        },
    }


class StressReservationsApiUser(HttpUser):
    wait_time = between(0.0, 0.02)

    @task
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
