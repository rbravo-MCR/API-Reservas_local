import asyncio
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
from reservas_api.domain import PaymentResult, ProviderResult
from reservas_api.domain.entities import Reservation
from reservas_api.infrastructure.outbox import OutboxEventProcessor, OutboxEventPublisher
from reservas_api.infrastructure.repositories import MySQLReservationRepository


class SpyPaymentGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def process_payment(self, reservation: Reservation) -> PaymentResult:
        self.calls += 1
        return PaymentResult(
            success=True,
            status="PAID",
            payload={"reservation_code": reservation.reservation_code.value},
        )


class SpyProviderGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def create_booking(self, reservation: Reservation) -> ProviderResult:
        self.calls += 1
        return ProviderResult(
            success=True,
            status="CONFIRMED",
            payload={"reservation_code": reservation.reservation_code.value},
        )


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


def _build_request(rental_days: int, amount: Decimal) -> CreateReservationRequest:
    pickup = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
    dropoff = pickup + timedelta(days=rental_days)
    return CreateReservationRequest(
        supplier_code="SUP01",
        pickup_office_code="OFF001",
        dropoff_office_code="OFF002",
        pickup_datetime=pickup,
        dropoff_datetime=dropoff,
        total_amount=amount,
        customer={
            "first_name": "Ana",
            "last_name": "Perez",
            "email": "ana@example.com",
            "phone": "+34000000000",
        },
        vehicle={"vehicle_code": "VH001", "model": "Corolla", "category": "Economy"},
    )


@settings(max_examples=10, deadline=None)
@given(
    rental_days=st.integers(min_value=1, max_value=10),
    amount=st.decimals(min_value=Decimal("10.00"), max_value=Decimal("2000.00"), places=2),
)
def test_property_9_payment_api_called_after_reservation_is_saved(
    mysql_test_urls: tuple[str, str],
    rental_days: int,
    amount: Decimal,
) -> None:
    """
    Feature: reservas-api, Property 9: Llamada a API de cobro despues de guardar reserva
    Validates: Requirements 4.1
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
            await use_case.execute(_build_request(rental_days=rental_days, amount=amount))

            payment_gateway = SpyPaymentGateway()
            processor = OutboxEventProcessor(
                session_factory=session_factory,
                payment_gateway=payment_gateway,
                provider_gateway=SpyProviderGateway(),
            )
            await processor.process_pending_once()

            assert payment_gateway.calls >= 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())


@settings(max_examples=10, deadline=None)
@given(
    rental_days=st.integers(min_value=1, max_value=10),
    amount=st.decimals(min_value=Decimal("10.00"), max_value=Decimal("2000.00"), places=2),
)
def test_property_12_provider_api_called_after_reservation_is_saved(
    mysql_test_urls: tuple[str, str],
    rental_days: int,
    amount: Decimal,
) -> None:
    """
    Feature: reservas-api, Property 12: Llamada a API de proveedor despues de guardar reserva
    Validates: Requirements 5.1
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
            await use_case.execute(_build_request(rental_days=rental_days, amount=amount))

            provider_gateway = SpyProviderGateway()
            processor = OutboxEventProcessor(
                session_factory=session_factory,
                payment_gateway=SpyPaymentGateway(),
                provider_gateway=provider_gateway,
            )
            await processor.process_pending_once()

            assert provider_gateway.calls >= 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())
