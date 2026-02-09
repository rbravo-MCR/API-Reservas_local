from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from reservas_api.application.use_cases import (
    CreateReservationPersistenceError,
    CreateReservationRequest,
    CreateReservationUseCase,
    ReservationCodeGenerationError,
)
from reservas_api.domain.entities import Reservation
from reservas_api.domain.value_objects import ReservationCode


class StubGenerateReservationCodeUseCase:
    def __init__(self, value: str = "AB12CD34") -> None:
        self._value = value

    async def execute(self) -> ReservationCode:
        return ReservationCode(self._value)


class FailingGenerateReservationCodeUseCase:
    async def execute(self) -> ReservationCode:
        raise ReservationCodeGenerationError("unable to generate code")


class SpyOutboxWriter:
    def __init__(self) -> None:
        self.saved_reservation: Reservation | None = None

    async def save_reservation_with_outbox(
        self,
        reservation: Reservation,
        events=None,
    ) -> Reservation:
        self.saved_reservation = reservation
        return reservation


class FailingOutboxWriter:
    async def save_reservation_with_outbox(
        self,
        reservation: Reservation,
        events=None,
    ) -> Reservation:
        raise RuntimeError("database unavailable")


def _build_request() -> CreateReservationRequest:
    pickup = datetime(2026, 4, 1, 10, 0, tzinfo=UTC)
    dropoff = pickup + timedelta(days=2)
    return CreateReservationRequest(
        supplier_code="SUP01",
        pickup_office_code="OFF001",
        dropoff_office_code="OFF002",
        pickup_datetime=pickup,
        dropoff_datetime=dropoff,
        total_amount=Decimal("180.50"),
        customer={
            "first_name": "Ana",
            "last_name": "Perez",
            "email": "ana@example.com",
            "phone": "+34123456789",
        },
        vehicle={"vehicle_code": "VH001", "model": "Corolla", "category": "Economy"},
    )


@pytest.mark.asyncio
async def test_create_reservation_use_case_creates_reservation_successfully() -> None:
    outbox_writer = SpyOutboxWriter()
    use_case = CreateReservationUseCase(
        generate_code_use_case=StubGenerateReservationCodeUseCase("ZX12CV90"),
        outbox_writer=outbox_writer,
    )

    result = await use_case.execute(_build_request())

    assert result.reservation_code.value == "ZX12CV90"
    assert outbox_writer.saved_reservation is not None
    assert outbox_writer.saved_reservation.supplier_code == "SUP01"
    assert outbox_writer.saved_reservation.customer_snapshot["email"] == "ana@example.com"


@pytest.mark.asyncio
async def test_create_reservation_use_case_raises_on_persistence_error() -> None:
    use_case = CreateReservationUseCase(
        generate_code_use_case=StubGenerateReservationCodeUseCase(),
        outbox_writer=FailingOutboxWriter(),
    )

    with pytest.raises(CreateReservationPersistenceError, match="Unable to persist reservation"):
        await use_case.execute(_build_request())


@pytest.mark.asyncio
async def test_create_reservation_use_case_propagates_code_generation_error() -> None:
    use_case = CreateReservationUseCase(
        generate_code_use_case=FailingGenerateReservationCodeUseCase(),
        outbox_writer=SpyOutboxWriter(),
    )

    with pytest.raises(ReservationCodeGenerationError):
        await use_case.execute(_build_request())


def test_create_reservation_request_rejects_invalid_input_data() -> None:
    pickup = datetime(2026, 4, 1, 10, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="dropoff_datetime must be after pickup_datetime"):
        CreateReservationRequest(
            supplier_code="SUP01",
            pickup_office_code="OFF001",
            dropoff_office_code="OFF002",
            pickup_datetime=pickup,
            dropoff_datetime=pickup,
            total_amount=Decimal("180.50"),
            customer={"first_name": "Ana", "last_name": "Perez", "email": "ana@example.com"},
            vehicle={"vehicle_code": "VH001", "model": "Corolla", "category": "Economy"},
        )

    with pytest.raises(ValueError, match="customer missing required keys: email"):
        CreateReservationRequest(
            supplier_code="SUP01",
            pickup_office_code="OFF001",
            dropoff_office_code="OFF002",
            pickup_datetime=pickup,
            dropoff_datetime=pickup + timedelta(days=1),
            total_amount=Decimal("180.50"),
            customer={"first_name": "Ana", "last_name": "Perez"},
            vehicle={"vehicle_code": "VH001", "model": "Corolla", "category": "Economy"},
        )
