from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from reservas_api.domain import DomainEvent, PaymentResult, ProviderResult
from reservas_api.domain.entities import Reservation
from reservas_api.domain.value_objects import ReservationCode
from reservas_api.infrastructure.db.models import ProviderOutboxEventModel
from reservas_api.infrastructure.outbox import OutboxEventProcessor, OutboxEventPublisher
from reservas_api.infrastructure.repositories import MySQLReservationRepository


class ControlledPaymentGateway:
    def __init__(self, failures_before_success: int = 0) -> None:
        self._failures_before_success = failures_before_success
        self.calls = 0

    async def process_payment(self, reservation: Reservation) -> PaymentResult:
        self.calls += 1
        if self.calls <= self._failures_before_success:
            raise RuntimeError("payment gateway unavailable")
        return PaymentResult(success=True, status="PAID", payload={"reservation": reservation.reservation_code.value})


class ControlledProviderGateway:
    def __init__(self, failures_before_success: int = 0) -> None:
        self._failures_before_success = failures_before_success
        self.calls = 0

    async def create_booking(self, reservation: Reservation) -> ProviderResult:
        self.calls += 1
        if self.calls <= self._failures_before_success:
            raise RuntimeError("provider gateway unavailable")
        return ProviderResult(
            success=True,
            status="CONFIRMED",
            payload={"reservation": reservation.reservation_code.value},
        )


def _build_reservation(code: str = "AB12CD34") -> Reservation:
    pickup = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)
    dropoff = pickup + timedelta(days=2)
    return Reservation(
        reservation_code=ReservationCode(code),
        supplier_code="SUP001",
        pickup_office_code="MAD01",
        dropoff_office_code="MAD02",
        pickup_datetime=pickup,
        dropoff_datetime=dropoff,
        total_amount=Decimal("220.00"),
        customer_snapshot={"first_name": "Ana", "email": "ana@example.com"},
        vehicle_snapshot={"vehicle_code": "VH001"},
    )


@pytest.mark.asyncio
async def test_outbox_publisher_saves_reservation_and_events_atomically(
    mysql_async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    publisher = OutboxEventPublisher(mysql_async_session_factory)
    repository = MySQLReservationRepository(mysql_async_session_factory)
    reservation = _build_reservation("OTBX0001")

    saved = await publisher.save_reservation_with_outbox(reservation)

    stored = await repository.find_by_code(ReservationCode("OTBX0001"))
    assert saved.id is not None
    assert stored is not None

    async with mysql_async_session_factory() as session:
        result = await session.exec(select(ProviderOutboxEventModel).order_by(ProviderOutboxEventModel.id))
        events = list(result.all())
    assert len(events) == 2
    assert {item.event_type for item in events} == {"PAYMENT_REQUESTED", "BOOKING_REQUESTED"}
    assert all(item.status == "PENDING" for item in events)


@pytest.mark.asyncio
async def test_outbox_atomic_transaction_rolls_back_reservation_if_event_insert_fails(
    mysql_async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    publisher = OutboxEventPublisher(mysql_async_session_factory)
    repository = MySQLReservationRepository(mysql_async_session_factory)
    reservation = _build_reservation("OTBX0002")
    invalid_events = [
        DomainEvent(  # type: ignore[arg-type]
            event_type=None,
            aggregate_id=reservation.reservation_code.value,
            payload={"reservation": {"reservation_code": reservation.reservation_code.value}},
        )
    ]

    with pytest.raises(IntegrityError):
        await publisher.save_reservation_with_outbox(reservation, invalid_events)

    stored = await repository.find_by_code(ReservationCode("OTBX0002"))
    assert stored is None


@pytest.mark.asyncio
async def test_outbox_processor_retries_failed_events_and_marks_processed_after_recovery(
    mysql_async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    reservation = _build_reservation("OTBX0003")
    publisher = OutboxEventPublisher(mysql_async_session_factory)
    await publisher.save_reservation_with_outbox(reservation)

    payment_gateway = ControlledPaymentGateway(failures_before_success=1)
    provider_gateway = ControlledProviderGateway(failures_before_success=0)
    processor = OutboxEventProcessor(
        session_factory=mysql_async_session_factory,
        payment_gateway=payment_gateway,
        provider_gateway=provider_gateway,
    )

    first_run_processed = await processor.process_pending_once()
    assert first_run_processed == 1

    async with mysql_async_session_factory() as session:
        result = await session.exec(select(ProviderOutboxEventModel))
        first_statuses = {item.event_type: item.status for item in result.all()}
    assert first_statuses["PAYMENT_REQUESTED"] == "FAILED"
    assert first_statuses["BOOKING_REQUESTED"] == "PROCESSED"

    second_run_processed = await processor.process_pending_once()
    assert second_run_processed == 1

    async with mysql_async_session_factory() as session:
        result = await session.exec(select(ProviderOutboxEventModel))
        final_statuses = {item.event_type: item.status for item in result.all()}
    assert final_statuses["PAYMENT_REQUESTED"] == "PROCESSED"
    assert final_statuses["BOOKING_REQUESTED"] == "PROCESSED"
    assert payment_gateway.calls == 2
    assert provider_gateway.calls == 1

