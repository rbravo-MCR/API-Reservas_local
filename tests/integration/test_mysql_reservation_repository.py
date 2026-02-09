from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from reservas_api.domain.entities import Reservation
from reservas_api.domain.enums import ReservationStatus
from reservas_api.domain.value_objects import ReservationCode
from reservas_api.infrastructure.repositories import (
    MySQLReservationRepository,
    ReservationNotFoundError,
)


def _build_reservation(code: str = "AB12CD34") -> Reservation:
    pickup = datetime(2026, 4, 1, 10, 0, tzinfo=UTC)
    dropoff = pickup + timedelta(days=2)
    return Reservation(
        reservation_code=ReservationCode(code),
        supplier_code="SUP-A",
        pickup_office_code="MAD-01",
        dropoff_office_code="MAD-02",
        pickup_datetime=pickup,
        dropoff_datetime=dropoff,
        total_amount=Decimal("180.00"),
        customer_snapshot={"first_name": "Ada", "email": "ada@example.com"},
        vehicle_snapshot={"vehicle_code": "VH001", "category": "ECONOMY"},
    )


@pytest.mark.asyncio
async def test_save_and_find_by_code(
    mysql_async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = MySQLReservationRepository(mysql_async_session_factory)
    reservation = _build_reservation("ZX98CV76")

    saved = await repository.save(reservation)
    found = await repository.find_by_code(ReservationCode("ZX98CV76"))

    assert saved.id is not None
    assert found is not None
    assert found.reservation_code.value == "ZX98CV76"
    assert found.status == ReservationStatus.CREATED


@pytest.mark.asyncio
async def test_exists_code_returns_true_when_present(
    mysql_async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = MySQLReservationRepository(mysql_async_session_factory)
    await repository.save(_build_reservation("QW12ER34"))

    exists = await repository.exists_code(ReservationCode("QW12ER34"))

    assert exists is True


@pytest.mark.asyncio
async def test_update_status_updates_persisted_value(
    mysql_async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = MySQLReservationRepository(mysql_async_session_factory)
    await repository.save(_build_reservation("PL09OK87"))

    await repository.update_status(ReservationCode("PL09OK87"), ReservationStatus.PAID)
    found = await repository.find_by_code(ReservationCode("PL09OK87"))

    assert found is not None
    assert found.status == ReservationStatus.PAID


@pytest.mark.asyncio
async def test_update_status_raises_when_reservation_missing(
    mysql_async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = MySQLReservationRepository(mysql_async_session_factory)

    with pytest.raises(ReservationNotFoundError):
        await repository.update_status(ReservationCode("NOPE1234"), ReservationStatus.PAID)
