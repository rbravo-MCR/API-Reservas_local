import asyncio
import string
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel.ext.asyncio.session import AsyncSession

from reservas_api.application.use_cases import (
    CreateReservationRequest,
    CreateReservationUseCase,
    GenerateReservationCodeUseCase,
)
from reservas_api.domain.enums import ReservationStatus
from reservas_api.infrastructure.outbox import OutboxEventPublisher
from reservas_api.infrastructure.repositories import MySQLReservationRepository

_ALNUM = string.ascii_uppercase + string.digits


def _sanitize_code_fragment(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch in _ALNUM)[:5] or "SUP01"


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


def _build_request(
    supplier: str,
    pickup_days_offset: int,
    rental_days: int,
    total_amount: Decimal,
) -> CreateReservationRequest:
    pickup = datetime(2026, 8, 1, 10, 0, tzinfo=UTC) + timedelta(days=pickup_days_offset)
    dropoff = pickup + timedelta(days=rental_days)
    supplier_code = _sanitize_code_fragment(supplier)
    return CreateReservationRequest(
        supplier_code=supplier_code,
        pickup_office_code=f"{supplier_code}P1",
        dropoff_office_code=f"{supplier_code}D1",
        pickup_datetime=pickup,
        dropoff_datetime=dropoff,
        total_amount=total_amount,
        customer={
            "first_name": "Ana",
            "last_name": "Perez",
            "email": "ana@example.com",
            "phone": "+34000000000",
        },
        vehicle={
            "vehicle_code": "VH001",
            "model": "Corolla",
            "category": "Economy",
        },
    )


@settings(max_examples=10, deadline=None)
@given(
    supplier=st.text(alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")), min_size=1, max_size=8),
    pickup_days_offset=st.integers(min_value=0, max_value=15),
    rental_days=st.integers(min_value=1, max_value=14),
    total_amount=st.decimals(min_value=Decimal("10.00"), max_value=Decimal("2000.00"), places=2),
)
def test_property_6_valid_data_results_in_successful_creation(
    mysql_test_urls: tuple[str, str],
    supplier: str,
    pickup_days_offset: int,
    rental_days: int,
    total_amount: Decimal,
) -> None:
    """
    Feature: reservas-api, Property 6: Datos validos resultan en creacion exitosa
    Validates: Requirements 2.4
    """

    async def scenario() -> None:
        async_url, _ = mysql_test_urls
        engine = create_async_engine(async_url, poolclass=NullPool, pool_pre_ping=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            await _truncate_reservation_tables(session_factory)
            repository = MySQLReservationRepository(session_factory)
            use_case = CreateReservationUseCase(
                generate_code_use_case=GenerateReservationCodeUseCase(repository=repository),
                outbox_writer=OutboxEventPublisher(session_factory),
            )
            created = await use_case.execute(
                _build_request(
                    supplier=supplier,
                    pickup_days_offset=pickup_days_offset,
                    rental_days=rental_days,
                    total_amount=total_amount,
                )
            )

            assert len(created.reservation_code.value) == 8
            assert created.reservation_code.value.isalnum()
            assert created.id is not None
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@settings(max_examples=10, deadline=None)
@given(
    supplier=st.text(alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")), min_size=1, max_size=8),
    pickup_days_offset=st.integers(min_value=0, max_value=10),
    rental_days=st.integers(min_value=1, max_value=10),
    total_amount=st.decimals(min_value=Decimal("20.00"), max_value=Decimal("1500.00"), places=2),
)
def test_property_7_persisted_reservation_contains_required_data(
    mysql_test_urls: tuple[str, str],
    supplier: str,
    pickup_days_offset: int,
    rental_days: int,
    total_amount: Decimal,
) -> None:
    """
    Feature: reservas-api, Property 7: Reserva persistida contiene datos requeridos
    Validates: Requirements 3.1, 3.2
    """

    async def scenario() -> None:
        async_url, _ = mysql_test_urls
        engine = create_async_engine(async_url, poolclass=NullPool, pool_pre_ping=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            await _truncate_reservation_tables(session_factory)
            repository = MySQLReservationRepository(session_factory)
            use_case = CreateReservationUseCase(
                generate_code_use_case=GenerateReservationCodeUseCase(repository=repository),
                outbox_writer=OutboxEventPublisher(session_factory),
            )
            request = _build_request(
                supplier=supplier,
                pickup_days_offset=pickup_days_offset,
                rental_days=rental_days,
                total_amount=total_amount,
            )
            created = await use_case.execute(request)
            stored = await repository.find_by_code(created.reservation_code)

            assert stored is not None
            assert stored.reservation_code.value == created.reservation_code.value
            assert stored.customer_snapshot["email"] == request.customer["email"]
            assert stored.vehicle_snapshot["vehicle_code"] == request.vehicle["vehicle_code"]
            assert stored.created_at is not None
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@settings(max_examples=10, deadline=None)
@given(
    supplier=st.text(alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")), min_size=1, max_size=8),
    pickup_days_offset=st.integers(min_value=0, max_value=12),
    rental_days=st.integers(min_value=1, max_value=12),
    total_amount=st.decimals(min_value=Decimal("30.00"), max_value=Decimal("3000.00"), places=2),
)
def test_property_8_initial_status_is_created(
    mysql_test_urls: tuple[str, str],
    supplier: str,
    pickup_days_offset: int,
    rental_days: int,
    total_amount: Decimal,
) -> None:
    """
    Feature: reservas-api, Property 8: Estado inicial de reserva es CREATED
    Validates: Requirements 3.3, 6.1
    """

    async def scenario() -> None:
        async_url, _ = mysql_test_urls
        engine = create_async_engine(async_url, poolclass=NullPool, pool_pre_ping=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            await _truncate_reservation_tables(session_factory)
            repository = MySQLReservationRepository(session_factory)
            use_case = CreateReservationUseCase(
                generate_code_use_case=GenerateReservationCodeUseCase(repository=repository),
                outbox_writer=OutboxEventPublisher(session_factory),
            )
            created = await use_case.execute(
                _build_request(
                    supplier=supplier,
                    pickup_days_offset=pickup_days_offset,
                    rental_days=rental_days,
                    total_amount=total_amount,
                )
            )
            stored = await repository.find_by_code(created.reservation_code)

            assert created.status == ReservationStatus.CREATED
            assert stored is not None
            assert stored.status == ReservationStatus.CREATED
        finally:
            await engine.dispose()

    asyncio.run(scenario())
