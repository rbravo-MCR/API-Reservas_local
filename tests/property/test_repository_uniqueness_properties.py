from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from reservas_api.domain.enums import ReservationStatus
from reservas_api.infrastructure.db.models import ReservationModel


@settings(max_examples=100, deadline=None)
@given(
    code=st.text(
        alphabet=st.characters(min_codepoint=48, max_codepoint=122).filter(str.isalnum),
        min_size=8,
        max_size=8,
    )
)
def test_property_2_reservation_code_uniqueness_constraint(mysql_sync_engine, code: str) -> None:
    """
    Feature: reservas-api, Property 2: Codigos de reserva son unicos
    Validates: Requirements 1.2, 1.3
    """
    pickup = datetime(2026, 5, 1, 10, 0, tzinfo=UTC)
    dropoff = pickup + timedelta(days=1)

    with Session(mysql_sync_engine) as session:
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        session.execute(text("TRUNCATE TABLE reservation_provider_requests"))
        session.execute(text("TRUNCATE TABLE reservation_contacts"))
        session.execute(text("TRUNCATE TABLE reservation_status_history"))
        session.execute(text("TRUNCATE TABLE provider_outbox_events"))
        session.execute(text("TRUNCATE TABLE reservations"))
        session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        session.commit()

        session.add(
            ReservationModel(
                reservation_code=code,
                status=ReservationStatus.CREATED,
                supplier_code="SUP01",
                pickup_office_code="OFF1",
                dropoff_office_code="OFF2",
                pickup_datetime=pickup,
                dropoff_datetime=dropoff,
                total_amount=Decimal("120.00"),
                customer_snapshot={"name": "A"},
                vehicle_snapshot={"vehicle_code": "V1"},
            )
        )
        session.commit()

        session.add(
            ReservationModel(
                reservation_code=code,
                status=ReservationStatus.CREATED,
                supplier_code="SUP02",
                pickup_office_code="OFF3",
                dropoff_office_code="OFF4",
                pickup_datetime=pickup,
                dropoff_datetime=dropoff,
                total_amount=Decimal("220.00"),
                customer_snapshot={"name": "B"},
                vehicle_snapshot={"vehicle_code": "V2"},
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
