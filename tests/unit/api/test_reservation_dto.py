from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from reservas_api.api.schemas import ReservationRequestDTO


def _valid_payload() -> dict:
    pickup = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)
    return {
        "supplier_code": "SUP001",
        "pickup_office_code": "MAD01",
        "dropoff_office_code": "MAD02",
        "pickup_datetime": pickup.isoformat(),
        "dropoff_datetime": (pickup + timedelta(days=2)).isoformat(),
        "total_amount": "199.99",
        "customer": {
            "first_name": "Ana",
            "last_name": "Lopez",
            "email": "ana@example.com",
            "phone": "+3411111111",
        },
        "vehicle": {
            "vehicle_code": "VH001",
            "model": "Toyota Corolla",
            "category": "Economy",
        },
    }


def test_reservation_request_dto_accepts_valid_payload() -> None:
    dto = ReservationRequestDTO.model_validate(_valid_payload())

    assert dto.supplier_code == "SUP001"
    assert dto.total_amount == Decimal("199.99")


def test_reservation_request_rejects_dropoff_before_pickup() -> None:
    payload = _valid_payload()
    payload["dropoff_datetime"] = (datetime(2026, 8, 10, 8, 0, tzinfo=UTC)).isoformat()

    with pytest.raises(ValidationError, match="dropoff_datetime must be after pickup_datetime"):
        ReservationRequestDTO.model_validate(payload)

