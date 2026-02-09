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

from reservas_api.application.use_cases import (
    UpdateReservationStatusRequest,
    UpdateReservationStatusUseCase,
)
from reservas_api.domain.entities import Reservation
from reservas_api.domain.enums import ReservationStatus
from reservas_api.domain.value_objects import ReservationCode
from reservas_api.infrastructure.db.models import ReservationStatusHistoryModel
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


@settings(max_examples=10, deadline=None)
@given(seconds_between=st.integers(min_value=1, max_value=120))
def test_property_25_status_change_history_is_complete(
    mysql_test_urls: tuple[str, str],
    seconds_between: int,
) -> None:
    """
    Feature: reservas-api, Property 25: Historial completo de cambios de estado
    Validates: Requirements 13.3
    """

    async def scenario() -> None:
        async_url, _ = mysql_test_urls
        engine = create_async_engine(async_url, poolclass=NullPool, pool_pre_ping=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            await _truncate_reservation_tables(session_factory)
            repository = MySQLReservationRepository(session_factory)
            reservation_code = uuid.uuid4().hex[:8].upper()
            saved = await repository.save(_build_reservation(reservation_code))
            status_use_case = UpdateReservationStatusUseCase(
                status_store=MySQLReservationStatusStore(session_factory)
            )

            payment_time = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
            provider_time = payment_time + timedelta(seconds=seconds_between)
            await status_use_case.execute(
                UpdateReservationStatusRequest(
                    reservation_code=saved.reservation_code,
                    request_type="PAYMENT",
                    provider_code="STRIPE",
                    success=True,
                    responded_at=payment_time,
                )
            )
            final_status = await status_use_case.execute(
                UpdateReservationStatusRequest(
                    reservation_code=saved.reservation_code,
                    request_type="BOOKING",
                    provider_code="SUP001",
                    success=True,
                    responded_at=provider_time,
                )
            )

            assert final_status == ReservationStatus.SUPPLIER_CONFIRMED
            async with session_factory() as session:
                result = await session.exec(
                    select(ReservationStatusHistoryModel)
                    .where(ReservationStatusHistoryModel.reservation_code == saved.reservation_code.value)
                    .order_by(ReservationStatusHistoryModel.id)
                )
                history_entries = list(result.all())

            assert len(history_entries) == 2
            assert history_entries[0].from_status == ReservationStatus.CREATED
            assert history_entries[0].to_status == ReservationStatus.PAID
            assert _normalize_utc(history_entries[0].changed_at) == payment_time
            assert history_entries[1].from_status == ReservationStatus.PAID
            assert history_entries[1].to_status == ReservationStatus.SUPPLIER_CONFIRMED
            assert _normalize_utc(history_entries[1].changed_at) == provider_time
        finally:
            await engine.dispose()

    asyncio.run(scenario())
