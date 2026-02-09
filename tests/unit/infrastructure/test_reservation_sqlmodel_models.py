from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from reservas_api.domain.enums import ReservationStatus
from reservas_api.infrastructure.db.models import (
    ProviderOutboxEventModel,
    ReservationContactModel,
    ReservationModel,
    ReservationProviderRequestModel,
)


def test_create_and_query_reservation_local_tables(reset_mysql_schema) -> None:
    pickup = datetime(2026, 3, 10, 10, 0, tzinfo=UTC)
    dropoff = pickup + timedelta(days=2)

    reservation = ReservationModel(
        reservation_code="A1B2C3D4",
        status=ReservationStatus.CREATED,
        supplier_code="SUP01",
        pickup_office_code="MAD01",
        dropoff_office_code="MAD02",
        pickup_datetime=pickup,
        dropoff_datetime=dropoff,
        total_amount=Decimal("150.00"),
        customer_snapshot={"name": "Ana"},
        vehicle_snapshot={"vehicle_code": "VH001"},
    )

    contact = ReservationContactModel(
        reservation_code="A1B2C3D4",
        first_name="Ana",
        last_name="Lopez",
        email="ana@example.com",
        phone="+34111111111",
    )

    provider_request = ReservationProviderRequestModel(
        reservation_code="A1B2C3D4",
        provider_code="PROV1",
        request_type="BOOKING",
        request_payload={"foo": "bar"},
        response_payload=None,
        status="PENDING",
    )

    outbox_event = ProviderOutboxEventModel(
        aggregate_id="A1B2C3D4",
        event_type="RESERVATION_CREATED",
        payload={"reservation_code": "A1B2C3D4"},
    )

    with Session(reset_mysql_schema) as session:
        session.add(reservation)
        session.commit()

        session.add(contact)
        session.add(provider_request)
        session.add(outbox_event)
        session.commit()

        stored = session.exec(
            select(ReservationModel).where(ReservationModel.reservation_code == "A1B2C3D4")
        ).one()
        assert stored.status == ReservationStatus.CREATED
        assert stored.total_amount == Decimal("150.00")


def test_reservation_code_must_be_unique(reset_mysql_schema) -> None:
    pickup = datetime(2026, 3, 10, 10, 0, tzinfo=UTC)
    dropoff = pickup + timedelta(days=1)

    with Session(reset_mysql_schema) as session:
        session.add(
            ReservationModel(
                reservation_code="ZZ11XX22",
                status=ReservationStatus.CREATED,
                supplier_code="SUP01",
                pickup_office_code="OFF1",
                dropoff_office_code="OFF2",
                pickup_datetime=pickup,
                dropoff_datetime=dropoff,
                total_amount=Decimal("80.00"),
                customer_snapshot={"name": "A"},
                vehicle_snapshot={"vehicle_code": "VH1"},
            )
        )
        session.commit()

        session.add(
            ReservationModel(
                reservation_code="ZZ11XX22",
                status=ReservationStatus.CREATED,
                supplier_code="SUP02",
                pickup_office_code="OFF3",
                dropoff_office_code="OFF4",
                pickup_datetime=pickup,
                dropoff_datetime=dropoff,
                total_amount=Decimal("90.00"),
                customer_snapshot={"name": "B"},
                vehicle_snapshot={"vehicle_code": "VH2"},
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
