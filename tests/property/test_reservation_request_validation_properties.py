from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from reservas_api.api.schemas import ReservationRequestDTO

REQUIRED_FIELDS = [
    "supplier_code",
    "pickup_office_code",
    "dropoff_office_code",
    "pickup_datetime",
    "dropoff_datetime",
    "total_amount",
    "customer",
    "vehicle",
]


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


@settings(max_examples=100, deadline=None)
@given(missing_field=st.sampled_from(REQUIRED_FIELDS))
def test_property_4_missing_required_fields_are_rejected(missing_field: str) -> None:
    """
    Feature: reservas-api, Property 4: Validacion rechaza campos obligatorios faltantes
    Validates: Requirements 2.1
    """
    payload = _valid_payload()
    payload.pop(missing_field, None)

    with pytest.raises(ValidationError):
        ReservationRequestDTO.model_validate(payload)


@settings(max_examples=100, deadline=None)
@given(
    invalid_supplier=st.one_of(st.integers(), st.booleans(), st.none()),
    invalid_pickup_datetime=st.one_of(st.integers(), st.floats(), st.booleans(), st.none()),
    invalid_total_amount=st.one_of(st.lists(st.integers()), st.dictionaries(st.text(), st.text())),
)
def test_property_5_invalid_types_are_rejected(
    invalid_supplier,
    invalid_pickup_datetime,
    invalid_total_amount,
) -> None:
    """
    Feature: reservas-api, Property 5: Validacion rechaza tipos de datos incorrectos
    Validates: Requirements 2.2
    """
    payload = _valid_payload()
    payload["supplier_code"] = invalid_supplier
    payload["pickup_datetime"] = invalid_pickup_datetime
    payload["total_amount"] = invalid_total_amount

    with pytest.raises(ValidationError):
        ReservationRequestDTO.model_validate(payload)

