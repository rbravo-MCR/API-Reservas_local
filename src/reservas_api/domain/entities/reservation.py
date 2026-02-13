from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from reservas_api.domain.enums import ReservationStatus
from reservas_api.domain.value_objects import ReservationCode


@dataclass(slots=True, frozen=True)
class ReservationAddon:
    """Persisted add-on line item within a reservation (with snapshot)."""

    addon_code: str
    addon_name_snapshot: str
    addon_category_snapshot: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    currency_code: str = "USD"


@dataclass(slots=True, frozen=True)
class ReservationStatusChange:
    """Represents one reservation status transition with timestamp."""

    from_status: ReservationStatus
    to_status: ReservationStatus
    changed_at: datetime


@dataclass(slots=True)
class Reservation:
    """Reservation aggregate root.

    Example:
        ```python
        reservation = Reservation(...)
        reservation.mark_payment_in_progress()
        ```
    """

    reservation_code: ReservationCode
    supplier_code: str
    pickup_office_code: str
    dropoff_office_code: str
    pickup_datetime: datetime
    dropoff_datetime: datetime
    total_amount: Decimal
    customer_snapshot: dict[str, Any]
    vehicle_snapshot: dict[str, Any]
    id: int | None = None
    status: ReservationStatus = ReservationStatus.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    addons: list[ReservationAddon] = field(default_factory=list)
    status_history: list[ReservationStatusChange] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.dropoff_datetime <= self.pickup_datetime:
            raise ValueError("dropoff_datetime must be after pickup_datetime")
        if self.total_amount <= Decimal("0"):
            raise ValueError("total_amount must be greater than zero")

    def mark_payment_in_progress(self) -> None:
        """Move status from `CREATED` to `PAYMENT_IN_PROGRESS`."""
        self._transition(
            current=ReservationStatus.CREATED,
            target=ReservationStatus.PAYMENT_IN_PROGRESS,
        )

    def mark_paid(self) -> None:
        """Move status from `PAYMENT_IN_PROGRESS` to `PAID`."""
        self._transition(
            current=ReservationStatus.PAYMENT_IN_PROGRESS,
            target=ReservationStatus.PAID,
        )

    def mark_supplier_confirmed(self) -> None:
        """Move status from `PAID` to `SUPPLIER_CONFIRMED`."""
        self._transition(
            current=ReservationStatus.PAID,
            target=ReservationStatus.SUPPLIER_CONFIRMED,
        )

    def can_be_cancelled(self) -> bool:
        """Return whether reservation can still be cancelled."""
        return self.status != ReservationStatus.CANCELLED

    def _transition(self, current: ReservationStatus, target: ReservationStatus) -> None:
        if self.status != current:
            raise ValueError(f"Invalid transition from {self.status} to {target}")
        previous_status = self.status
        self.status = target
        self.status_history.append(
            ReservationStatusChange(
                from_status=previous_status,
                to_status=target,
                changed_at=datetime.now(UTC),
            )
        )
