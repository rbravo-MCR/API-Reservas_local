from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from reservas_api.domain.entities import Reservation
from reservas_api.domain.enums import ReservationStatus
from reservas_api.domain.value_objects import ReservationCode


def _build_reservation() -> Reservation:
    pickup = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
    dropoff = pickup + timedelta(days=3)
    return Reservation(
        reservation_code=ReservationCode("A1B2C3D4"),
        supplier_code="SUP01",
        pickup_office_code="OFF001",
        dropoff_office_code="OFF002",
        pickup_datetime=pickup,
        dropoff_datetime=dropoff,
        total_amount=Decimal("250.00"),
        customer_snapshot={"first_name": "Ana", "email": "ana@example.com"},
        vehicle_snapshot={"vehicle_code": "VH001", "category": "Economy"},
    )


def test_reservation_starts_in_created_status() -> None:
    reservation = _build_reservation()

    assert reservation.status == ReservationStatus.CREATED


def test_mark_payment_in_progress_updates_state_and_history() -> None:
    reservation = _build_reservation()

    reservation.mark_payment_in_progress()

    assert reservation.status == ReservationStatus.PAYMENT_IN_PROGRESS
    assert len(reservation.status_history) == 1
    assert reservation.status_history[0].from_status == ReservationStatus.CREATED
    assert reservation.status_history[0].to_status == ReservationStatus.PAYMENT_IN_PROGRESS


def test_mark_paid_requires_payment_in_progress() -> None:
    reservation = _build_reservation()

    with pytest.raises(ValueError, match="Invalid transition"):
        reservation.mark_paid()


def test_mark_supplier_confirmed_requires_paid() -> None:
    reservation = _build_reservation()
    reservation.mark_payment_in_progress()

    with pytest.raises(ValueError, match="Invalid transition"):
        reservation.mark_supplier_confirmed()


def test_can_be_cancelled_returns_false_when_cancelled() -> None:
    reservation = _build_reservation()
    reservation.status = ReservationStatus.CANCELLED

    assert reservation.can_be_cancelled() is False


def test_create_reservation_with_invalid_dates_fails() -> None:
    pickup = datetime(2026, 3, 3, 10, 0, tzinfo=UTC)
    dropoff = pickup - timedelta(hours=1)

    with pytest.raises(ValueError, match="dropoff_datetime must be after pickup_datetime"):
        Reservation(
            reservation_code=ReservationCode("Q1W2E3R4"),
            supplier_code="SUP01",
            pickup_office_code="OFF001",
            dropoff_office_code="OFF002",
            pickup_datetime=pickup,
            dropoff_datetime=dropoff,
            total_amount=Decimal("250.00"),
            customer_snapshot={"first_name": "Ana", "email": "ana@example.com"},
            vehicle_snapshot={"vehicle_code": "VH001", "category": "Economy"},
        )


def test_create_reservation_with_non_positive_amount_fails() -> None:
    pickup = datetime(2026, 3, 3, 10, 0, tzinfo=UTC)
    dropoff = pickup + timedelta(days=1)

    with pytest.raises(ValueError, match="total_amount must be greater than zero"):
        Reservation(
            reservation_code=ReservationCode("Z9X8C7V6"),
            supplier_code="SUP01",
            pickup_office_code="OFF001",
            dropoff_office_code="OFF002",
            pickup_datetime=pickup,
            dropoff_datetime=dropoff,
            total_amount=Decimal("0"),
            customer_snapshot={"first_name": "Ana", "email": "ana@example.com"},
            vehicle_snapshot={"vehicle_code": "VH001", "category": "Economy"},
        )

