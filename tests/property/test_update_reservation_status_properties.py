import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from hypothesis import assume, given, settings
from hypothesis import strategies as st
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from reservas_api.application.use_cases import (
    UpdateReservationStatusRequest,
    UpdateReservationStatusUseCase,
)
from reservas_api.domain.entities import Reservation
from reservas_api.domain.enums import ReservationStatus
from reservas_api.domain.value_objects import ReservationCode
from reservas_api.infrastructure.db.models import ReservationProviderRequestModel
from reservas_api.infrastructure.repositories import (
    MySQLReservationRepository,
    MySQLReservationStatusStore,
)


def _normalize_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def _truncate_reservation_tables(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        async with session.begin():
            await session.exec(text("SET FOREIGN_KEY_CHECKS = 0"))
            await session.exec(text("TRUNCATE TABLE reservation_provider_requests"))
            await session.exec(text("TRUNCATE TABLE reservation_contacts"))
            await session.exec(text("TRUNCATE TABLE reservation_status_history"))
            await session.exec(text("TRUNCATE TABLE provider_outbox_events"))
            await session.exec(text("TRUNCATE TABLE reservations"))
            await session.exec(text("SET FOREIGN_KEY_CHECKS = 1"))


def _build_reservation(code: str) -> Reservation:
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


async def _create_base_reservation(
    session_factory: async_sessionmaker[AsyncSession],
) -> ReservationCode:
    repository = MySQLReservationRepository(session_factory)
    code = uuid.uuid4().hex[:8].upper()
    reservation = _build_reservation(code)
    saved = await repository.save(reservation)
    return saved.reservation_code


@settings(max_examples=8, deadline=None)
@given(payment_success=st.booleans())
def test_property_10_status_updates_from_payment_response(
    mysql_test_urls: tuple[str, str],
    payment_success: bool,
) -> None:
    """
    Feature: reservas-api, Property 10: Actualizacion de estado segun respuesta de API de cobro
    Validates: Requirements 4.2
    """

    async def scenario() -> None:
        async_url, _ = mysql_test_urls
        engine = create_async_engine(async_url, poolclass=NullPool, pool_pre_ping=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            await _truncate_reservation_tables(session_factory)
            reservation_code = await _create_base_reservation(session_factory)
            status_store = MySQLReservationStatusStore(session_factory)
            use_case = UpdateReservationStatusUseCase(status_store=status_store)

            resulting_status = await use_case.execute(
                UpdateReservationStatusRequest(
                    reservation_code=reservation_code,
                    request_type="PAYMENT",
                    provider_code="STRIPE",
                    success=payment_success,
                    request_payload={"amount": "220.00"},
                    response_payload={"status": "PAID" if payment_success else "FAILED"},
                )
            )

            repository = MySQLReservationRepository(session_factory)
            stored = await repository.find_by_code(reservation_code)
            assert stored is not None
            expected = ReservationStatus.PAID if payment_success else ReservationStatus.CREATED
            assert resulting_status == expected
            assert stored.status == expected

            async with session_factory() as session:
                result = await session.exec(
                    select(ReservationProviderRequestModel).where(
                        ReservationProviderRequestModel.reservation_code == reservation_code.value,
                        ReservationProviderRequestModel.request_type == "PAYMENT",
                    )
                )
                saved_request = result.one()
            assert saved_request.status == ("SUCCESS" if payment_success else "FAILED")
            assert saved_request.response_payload == {
                "status": "PAID" if payment_success else "FAILED"
            }
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@settings(max_examples=8, deadline=None)
@given(provider_success=st.booleans())
def test_property_13_status_updates_from_provider_response(
    mysql_test_urls: tuple[str, str],
    provider_success: bool,
) -> None:
    """
    Feature: reservas-api, Property 13: Actualizacion de estado segun respuesta de API de proveedor
    Validates: Requirements 5.2
    """

    async def scenario() -> None:
        async_url, _ = mysql_test_urls
        engine = create_async_engine(async_url, poolclass=NullPool, pool_pre_ping=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            await _truncate_reservation_tables(session_factory)
            reservation_code = await _create_base_reservation(session_factory)
            status_store = MySQLReservationStatusStore(session_factory)
            use_case = UpdateReservationStatusUseCase(status_store=status_store)

            await use_case.execute(
                UpdateReservationStatusRequest(
                    reservation_code=reservation_code,
                    request_type="PAYMENT",
                    provider_code="STRIPE",
                    success=True,
                    response_payload={"status": "PAID"},
                )
            )
            resulting_status = await use_case.execute(
                UpdateReservationStatusRequest(
                    reservation_code=reservation_code,
                    request_type="BOOKING",
                    provider_code="SUP001",
                    success=provider_success,
                    response_payload={"status": "CONFIRMED" if provider_success else "REJECTED"},
                )
            )

            repository = MySQLReservationRepository(session_factory)
            stored = await repository.find_by_code(reservation_code)
            assert stored is not None
            expected = (
                ReservationStatus.SUPPLIER_CONFIRMED
                if provider_success
                else ReservationStatus.PAID
            )
            assert resulting_status == expected
            assert stored.status == expected
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@settings(max_examples=8, deadline=None)
@given(seconds_between=st.integers(min_value=1, max_value=120))
def test_property_17_status_changes_register_timestamp(
    mysql_test_urls: tuple[str, str],
    seconds_between: int,
) -> None:
    """
    Feature: reservas-api, Property 17: Timestamp en cada cambio de estado
    Validates: Requirements 6.4
    """

    async def scenario() -> None:
        async_url, _ = mysql_test_urls
        engine = create_async_engine(async_url, poolclass=NullPool, pool_pre_ping=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            await _truncate_reservation_tables(session_factory)
            reservation_code = await _create_base_reservation(session_factory)
            status_store = MySQLReservationStatusStore(session_factory)
            use_case = UpdateReservationStatusUseCase(status_store=status_store)

            payment_time = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
            provider_time = payment_time + timedelta(seconds=seconds_between)
            await use_case.execute(
                UpdateReservationStatusRequest(
                    reservation_code=reservation_code,
                    request_type="PAYMENT",
                    provider_code="STRIPE",
                    success=True,
                    response_payload={"status": "PAID"},
                    responded_at=payment_time,
                )
            )
            await use_case.execute(
                UpdateReservationStatusRequest(
                    reservation_code=reservation_code,
                    request_type="BOOKING",
                    provider_code="SUP001",
                    success=True,
                    response_payload={"status": "CONFIRMED"},
                    responded_at=provider_time,
                )
            )

            async with session_factory() as session:
                result = await session.exec(
                    select(ReservationProviderRequestModel)
                    .where(ReservationProviderRequestModel.reservation_code == reservation_code.value)
                    .order_by(ReservationProviderRequestModel.id)
                )
                events = result.all()

            assert len(events) == 2
            assert _normalize_utc(events[0].responded_at) == payment_time
            assert _normalize_utc(events[1].responded_at) == provider_time
            assert all(event.responded_at is not None for event in events)
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@settings(max_examples=10, deadline=None)
@given(payment_success=st.booleans(), provider_success=st.booleans())
def test_property_15_confirmed_only_when_both_apis_succeed(
    mysql_test_urls: tuple[str, str],
    payment_success: bool,
    provider_success: bool,
) -> None:
    """
    Feature: reservas-api, Property 15: Reserva confirmada solo con ambas APIs exitosas
    Validates: Requirements 6.2
    """

    async def scenario() -> None:
        async_url, _ = mysql_test_urls
        engine = create_async_engine(async_url, poolclass=NullPool, pool_pre_ping=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            await _truncate_reservation_tables(session_factory)
            reservation_code = await _create_base_reservation(session_factory)
            use_case = UpdateReservationStatusUseCase(
                status_store=MySQLReservationStatusStore(session_factory)
            )

            await use_case.execute(
                UpdateReservationStatusRequest(
                    reservation_code=reservation_code,
                    request_type="PAYMENT",
                    provider_code="STRIPE",
                    success=payment_success,
                )
            )
            final_status = await use_case.execute(
                UpdateReservationStatusRequest(
                    reservation_code=reservation_code,
                    request_type="BOOKING",
                    provider_code="SUP001",
                    success=provider_success,
                )
            )

            assert (
                final_status == ReservationStatus.SUPPLIER_CONFIRMED
            ) is (payment_success and provider_success)
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@settings(max_examples=10, deadline=None)
@given(payment_success=st.booleans(), provider_success=st.booleans())
def test_property_16_not_confirmed_while_any_success_response_is_missing(
    mysql_test_urls: tuple[str, str],
    payment_success: bool,
    provider_success: bool,
) -> None:
    """
    Feature: reservas-api, Property 16: Reserva incompleta mientras falten respuestas
    Validates: Requirements 6.3
    """

    assume(not (payment_success and provider_success))

    async def scenario() -> None:
        async_url, _ = mysql_test_urls
        engine = create_async_engine(async_url, poolclass=NullPool, pool_pre_ping=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            await _truncate_reservation_tables(session_factory)
            reservation_code = await _create_base_reservation(session_factory)
            use_case = UpdateReservationStatusUseCase(
                status_store=MySQLReservationStatusStore(session_factory)
            )
            await use_case.execute(
                UpdateReservationStatusRequest(
                    reservation_code=reservation_code,
                    request_type="PAYMENT",
                    provider_code="STRIPE",
                    success=payment_success,
                )
            )
            final_status = await use_case.execute(
                UpdateReservationStatusRequest(
                    reservation_code=reservation_code,
                    request_type="BOOKING",
                    provider_code="SUP001",
                    success=provider_success,
                )
            )

            assert final_status != ReservationStatus.SUPPLIER_CONFIRMED
        finally:
            await engine.dispose()

    asyncio.run(scenario())
