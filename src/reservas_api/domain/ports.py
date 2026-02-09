from dataclasses import dataclass
from typing import Any, Protocol

from reservas_api.domain.entities import Reservation
from reservas_api.domain.enums import ReservationStatus
from reservas_api.domain.value_objects import ReservationCode


@dataclass(slots=True, frozen=True)
class PaymentResult:
    success: bool
    status: str
    payload: dict[str, Any] | None = None


@dataclass(slots=True, frozen=True)
class ProviderResult:
    success: bool
    status: str
    payload: dict[str, Any] | None = None


@dataclass(slots=True, frozen=True)
class DomainEvent:
    event_type: str
    aggregate_id: str
    payload: dict[str, Any] | None = None


class ReservationRepository(Protocol):
    async def save(self, reservation: Reservation) -> Reservation: ...

    async def find_by_code(self, code: ReservationCode) -> Reservation | None: ...

    async def exists_code(self, code: ReservationCode) -> bool: ...

    async def update_status(self, code: ReservationCode, status: ReservationStatus) -> None: ...


class PaymentGateway(Protocol):
    async def process_payment(self, reservation: Reservation) -> PaymentResult: ...


class ProviderGateway(Protocol):
    async def create_booking(self, reservation: Reservation) -> ProviderResult: ...


class EventPublisher(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...

