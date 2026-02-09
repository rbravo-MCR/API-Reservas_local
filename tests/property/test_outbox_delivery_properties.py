import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from reservas_api.domain import PaymentResult, ProviderResult
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


def _build_reservation() -> Reservation:
    pickup = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
    dropoff = pickup + timedelta(days=2)
    code = uuid.uuid4().hex[:8].upper()
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


async def _truncate_outbox_related_tables(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        async with session.begin():
            await session.exec(text("SET FOREIGN_KEY_CHECKS = 0"))
            await session.exec(text("TRUNCATE TABLE reservation_provider_requests"))
            await session.exec(text("TRUNCATE TABLE reservation_contacts"))
            await session.exec(text("TRUNCATE TABLE reservation_status_history"))
            await session.exec(text("TRUNCATE TABLE provider_outbox_events"))
            await session.exec(text("TRUNCATE TABLE reservations"))
            await session.exec(text("SET FOREIGN_KEY_CHECKS = 1"))


@settings(max_examples=8, deadline=None)
@given(failure_attempts=st.integers(min_value=1, max_value=3))
def test_property_18_reservation_created_even_when_external_calls_fail(
    mysql_test_urls: tuple[str, str],
    failure_attempts: int,
) -> None:
    """
    Feature: reservas-api, Property 18: Reserva creada aunque APIs externas fallen
    Validates: Requirements 7.4, 10.4
    """

    async def scenario() -> None:
        async_url, _ = mysql_test_urls
        engine = create_async_engine(async_url, poolclass=NullPool, pool_pre_ping=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            await _truncate_outbox_related_tables(session_factory)
            reservation = _build_reservation()
            publisher = OutboxEventPublisher(session_factory)
            repository = MySQLReservationRepository(session_factory)
            await publisher.save_reservation_with_outbox(reservation)

            processor = OutboxEventProcessor(
                session_factory=session_factory,
                payment_gateway=ControlledPaymentGateway(failures_before_success=failure_attempts),
                provider_gateway=ControlledProviderGateway(failures_before_success=0),
            )
            await processor.process_pending_once()

            stored = await repository.find_by_code(reservation.reservation_code)
            assert stored is not None

            async with session_factory() as session:
                result = await session.exec(select(ProviderOutboxEventModel))
                statuses = [item.status for item in result.all()]
            assert any(status == "FAILED" for status in statuses)
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@settings(max_examples=8, deadline=None)
@given(failure_attempts=st.integers(min_value=1, max_value=3))
def test_property_21_pending_reservations_processed_when_service_recovers(
    mysql_test_urls: tuple[str, str],
    failure_attempts: int,
) -> None:
    """
    Feature: reservas-api, Property 21: Procesamiento automatico de reservas pendientes
    Validates: Requirements 10.6
    """

    async def scenario() -> None:
        async_url, _ = mysql_test_urls
        engine = create_async_engine(async_url, poolclass=NullPool, pool_pre_ping=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            await _truncate_outbox_related_tables(session_factory)
            reservation = _build_reservation()
            publisher = OutboxEventPublisher(session_factory)
            await publisher.save_reservation_with_outbox(reservation)

            processor = OutboxEventProcessor(
                session_factory=session_factory,
                payment_gateway=ControlledPaymentGateway(failures_before_success=failure_attempts),
                provider_gateway=ControlledProviderGateway(failures_before_success=0),
            )

            for _ in range(failure_attempts + 2):
                await processor.process_pending_once()

            async with session_factory() as session:
                result = await session.exec(select(ProviderOutboxEventModel))
                statuses = [item.status for item in result.all()]
            assert statuses
            assert all(status == "PROCESSED" for status in statuses)
        finally:
            await engine.dispose()

    asyncio.run(scenario())
