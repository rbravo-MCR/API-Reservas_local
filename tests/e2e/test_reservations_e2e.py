import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from reservas_api.api.routers.reservations import get_create_reservation_use_case
from reservas_api.application import CreateReservationUseCase, GenerateReservationCodeUseCase
from reservas_api.domain import PaymentResult, ProviderResult
from reservas_api.domain.entities import Reservation
from reservas_api.infrastructure.db.models import ProviderOutboxEventModel, ReservationModel
from reservas_api.infrastructure.outbox import OutboxEventProcessor, OutboxEventPublisher
from reservas_api.infrastructure.repositories import MySQLReservationRepository
from reservas_api.main import app


class AlwaysFailPaymentGateway:
    async def process_payment(self, reservation: Reservation) -> PaymentResult:
        raise RuntimeError(f"payment unavailable for {reservation.reservation_code.value}")


class AlwaysFailProviderGateway:
    async def create_booking(self, reservation: Reservation) -> ProviderResult:
        raise RuntimeError(f"provider unavailable for {reservation.reservation_code.value}")


class FailOncePaymentGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def process_payment(self, reservation: Reservation) -> PaymentResult:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary payment outage")
        return PaymentResult(success=True, status="PAID", payload={"code": reservation.reservation_code.value})


class FailOnceProviderGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def create_booking(self, reservation: Reservation) -> ProviderResult:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary provider outage")
        return ProviderResult(
            success=True,
            status="CONFIRMED",
            payload={"code": reservation.reservation_code.value},
        )


@pytest.fixture
def e2e_client(mysql_async_session_factory: async_sessionmaker[AsyncSession]):
    def _use_case_factory() -> CreateReservationUseCase:
        repository = MySQLReservationRepository(mysql_async_session_factory)
        generate_code = GenerateReservationCodeUseCase(repository=repository)
        outbox_writer = OutboxEventPublisher(mysql_async_session_factory)
        return CreateReservationUseCase(
            generate_code_use_case=generate_code,
            outbox_writer=outbox_writer,
        )

    app.dependency_overrides[get_create_reservation_use_case] = _use_case_factory
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


def _valid_payload() -> dict:
    pickup = datetime(2026, 12, 1, 10, 0, tzinfo=UTC)
    dropoff = pickup + timedelta(days=2)
    return {
        "supplier_code": "SUP01",
        "pickup_office_code": "MAD01",
        "dropoff_office_code": "MAD02",
        "pickup_datetime": pickup.isoformat(),
        "dropoff_datetime": dropoff.isoformat(),
        "total_amount": "180.50",
        "customer": {
            "first_name": "Ana",
            "last_name": "Perez",
            "email": "ana@example.com",
            "phone": "+34123456789",
        },
        "vehicle": {
            "vehicle_code": "VH001",
            "model": "Corolla",
            "category": "Economy",
        },
    }


async def _load_outbox_statuses(
    session_factory: async_sessionmaker[AsyncSession],
    reservation_code: str,
) -> list[str]:
    async with session_factory() as session:
        query = (
            select(ProviderOutboxEventModel.status)
            .where(ProviderOutboxEventModel.aggregate_id == reservation_code)
            .order_by(ProviderOutboxEventModel.id)
        )
        result = await session.exec(query)
        return list(result.all())


@pytest.mark.asyncio
async def test_e2e_create_reservation_persists_and_enqueues_events(
    e2e_client: TestClient,
    mysql_async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    response = e2e_client.post("/api/v1/reservations", json=_valid_payload())

    assert response.status_code == 201
    body = response.json()
    reservation_code = body["reservation_code"]
    assert Decimal(body["total_amount"]) == Decimal("180.50")

    async with mysql_async_session_factory() as session:
        reservation_query = select(ReservationModel).where(
            ReservationModel.reservation_code == reservation_code
        )
        reservation = (await session.exec(reservation_query)).one_or_none()
        outbox_query = select(ProviderOutboxEventModel).where(
            ProviderOutboxEventModel.aggregate_id == reservation_code
        )
        outbox_events = list((await session.exec(outbox_query)).all())

    assert reservation is not None
    assert reservation.supplier_code == "SUP01"
    assert len(outbox_events) == 2
    assert {event.event_type for event in outbox_events} == {"PAYMENT_REQUESTED", "BOOKING_REQUESTED"}
    assert all(event.status == "PENDING" for event in outbox_events)


@pytest.mark.asyncio
async def test_e2e_outbox_marks_events_failed_when_external_gateways_fail(
    e2e_client: TestClient,
    mysql_async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    response = e2e_client.post("/api/v1/reservations", json=_valid_payload())
    reservation_code = response.json()["reservation_code"]

    processor = OutboxEventProcessor(
        session_factory=mysql_async_session_factory,
        payment_gateway=AlwaysFailPaymentGateway(),
        provider_gateway=AlwaysFailProviderGateway(),
        poll_interval_seconds=0.05,
        batch_size=10,
    )
    processed = await processor.process_pending_once(limit=10)
    statuses = await _load_outbox_statuses(mysql_async_session_factory, reservation_code)

    assert processed == 0
    assert statuses == ["FAILED", "FAILED"]


@pytest.mark.asyncio
async def test_e2e_outbox_recovers_automatically_after_transient_failures(
    e2e_client: TestClient,
    mysql_async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    response = e2e_client.post("/api/v1/reservations", json=_valid_payload())
    reservation_code = response.json()["reservation_code"]

    payment_gateway = FailOncePaymentGateway()
    provider_gateway = FailOnceProviderGateway()
    processor = OutboxEventProcessor(
        session_factory=mysql_async_session_factory,
        payment_gateway=payment_gateway,
        provider_gateway=provider_gateway,
        poll_interval_seconds=0.05,
        batch_size=10,
    )

    for _ in range(12):
        await processor.process_pending_once(limit=10)
        statuses = await _load_outbox_statuses(mysql_async_session_factory, reservation_code)
        if statuses == ["PROCESSED", "PROCESSED"]:
            break
        await asyncio.sleep(0.02)

    statuses = await _load_outbox_statuses(mysql_async_session_factory, reservation_code)
    assert statuses == ["PROCESSED", "PROCESSED"]
    assert payment_gateway.calls >= 2
    assert provider_gateway.calls >= 2
