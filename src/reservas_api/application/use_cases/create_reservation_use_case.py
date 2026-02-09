from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

from reservas_api.application.use_cases.generate_reservation_code_use_case import (
    GenerateReservationCodeUseCase,
)
from reservas_api.domain.entities import Reservation
from reservas_api.domain.ports import DomainEvent
from reservas_api.shared.security import (
    enforce_pci_storage_rules,
    sanitize_and_validate_payload,
    sanitize_and_validate_text,
)


class CreateReservationPersistenceError(RuntimeError):
    """Raised when reservation+outbox atomic persistence fails."""

    pass


class ReservationOutboxWriter(Protocol):
    """Port for atomic persistence of reservation and outbox events."""

    async def save_reservation_with_outbox(
        self,
        reservation: Reservation,
        events: Iterable[DomainEvent] | None = None,
    ) -> Reservation: ...


class CreateReservationAuditLogger(Protocol):
    """Port for audit events emitted during reservation creation."""

    def log_reservation_created(
        self,
        *,
        reservation_code: str,
        actor: str,
        context: dict[str, Any] | None = None,
    ) -> None: ...


@dataclass(slots=True, frozen=True)
class CreateReservationRequest:
    """Application input model to create a reservation."""

    supplier_code: str
    pickup_office_code: str
    dropoff_office_code: str
    pickup_datetime: datetime
    dropoff_datetime: datetime
    total_amount: Decimal
    customer: dict[str, Any]
    vehicle: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.supplier_code.strip():
            raise ValueError("supplier_code must not be empty")
        if not self.pickup_office_code.strip():
            raise ValueError("pickup_office_code must not be empty")
        if not self.dropoff_office_code.strip():
            raise ValueError("dropoff_office_code must not be empty")
        if self.dropoff_datetime <= self.pickup_datetime:
            raise ValueError("dropoff_datetime must be after pickup_datetime")
        if self.total_amount <= Decimal("0"):
            raise ValueError("total_amount must be greater than zero")
        if not isinstance(self.customer, dict):
            raise ValueError("customer must be a dict")
        if not isinstance(self.vehicle, dict):
            raise ValueError("vehicle must be a dict")

        required_customer_keys = {"first_name", "last_name", "email"}
        missing_customer = required_customer_keys.difference(self.customer)
        if missing_customer:
            missing = ", ".join(sorted(missing_customer))
            raise ValueError(f"customer missing required keys: {missing}")

        required_vehicle_keys = {"vehicle_code", "model", "category"}
        missing_vehicle = required_vehicle_keys.difference(self.vehicle)
        if missing_vehicle:
            missing = ", ".join(sorted(missing_vehicle))
            raise ValueError(f"vehicle missing required keys: {missing}")


class CreateReservationUseCase:
    """Create reservation with sanitization, PCI checks and outbox dispatch.

    Example:
        ```python
        request = CreateReservationRequest(...)
        created = await CreateReservationUseCase(...).execute(request)
        print(created.reservation_code.value)
        ```
    """

    def __init__(
        self,
        generate_code_use_case: GenerateReservationCodeUseCase,
        outbox_writer: ReservationOutboxWriter,
        audit_logger: CreateReservationAuditLogger | None = None,
    ) -> None:
        self._generate_code_use_case = generate_code_use_case
        self._outbox_writer = outbox_writer
        self._audit_logger = audit_logger

    async def execute(self, request: CreateReservationRequest) -> Reservation:
        """Create and persist a reservation from validated input."""
        reservation_code = await self._generate_code_use_case.execute()
        supplier_code = sanitize_and_validate_text(request.supplier_code)
        pickup_office_code = sanitize_and_validate_text(request.pickup_office_code)
        dropoff_office_code = sanitize_and_validate_text(request.dropoff_office_code)
        customer_snapshot = enforce_pci_storage_rules(
            sanitize_and_validate_payload(dict(request.customer))
        )
        vehicle_snapshot = enforce_pci_storage_rules(
            sanitize_and_validate_payload(dict(request.vehicle))
        )
        reservation = Reservation(
            reservation_code=reservation_code,
            supplier_code=supplier_code,
            pickup_office_code=pickup_office_code,
            dropoff_office_code=dropoff_office_code,
            pickup_datetime=request.pickup_datetime,
            dropoff_datetime=request.dropoff_datetime,
            total_amount=request.total_amount,
            customer_snapshot=customer_snapshot,
            vehicle_snapshot=vehicle_snapshot,
        )
        try:
            saved = await self._outbox_writer.save_reservation_with_outbox(reservation)
            if self._audit_logger is not None:
                self._audit_logger.log_reservation_created(
                    reservation_code=saved.reservation_code.value,
                    actor="system",
                    context={
                        "status": saved.status.value,
                        "supplier_code": saved.supplier_code,
                        "pickup_office_code": saved.pickup_office_code,
                        "dropoff_office_code": saved.dropoff_office_code,
                    },
                )
            return saved
        except Exception as exc:
            raise CreateReservationPersistenceError(
                "Unable to persist reservation and publish outbox events"
            ) from exc
