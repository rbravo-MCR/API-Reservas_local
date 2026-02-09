from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from reservas_api.domain.enums import ReservationStatus
from reservas_api.domain.value_objects import ReservationCode

ExternalRequestType = Literal["PAYMENT", "BOOKING"]


class ReservationStatusUpdateNotFoundError(ValueError):
    """Raised when target reservation does not exist."""

    pass


@dataclass(slots=True, frozen=True)
class UpdateReservationStatusRequest:
    """Input model for external response/status updates."""

    reservation_code: ReservationCode
    request_type: ExternalRequestType
    provider_code: str
    success: bool
    request_payload: dict[str, Any] | None = None
    response_payload: dict[str, Any] | None = None
    responded_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.provider_code.strip():
            raise ValueError("provider_code must not be empty")
        if self.responded_at is not None and self.responded_at.tzinfo is None:
            raise ValueError("responded_at must be timezone-aware")


class ReservationStatusStore(Protocol):
    """Port to persist request payloads and reservation status transitions."""

    async def get_status(self, reservation_code: ReservationCode) -> ReservationStatus: ...

    async def has_successful_request(
        self,
        reservation_code: ReservationCode,
        request_type: ExternalRequestType,
    ) -> bool: ...

    async def save_external_response(
        self,
        reservation_code: ReservationCode,
        provider_code: str,
        request_type: ExternalRequestType,
        success: bool,
        request_payload: dict[str, Any] | None,
        response_payload: dict[str, Any] | None,
        responded_at: datetime,
    ) -> None: ...

    async def set_status(
        self,
        reservation_code: ReservationCode,
        from_status: ReservationStatus,
        status: ReservationStatus,
        changed_at: datetime,
    ) -> None: ...


class UpdateReservationAuditLogger(Protocol):
    """Port for audit events emitted in status update flow."""

    def log_reservation_modified(
        self,
        *,
        reservation_code: str,
        actor: str,
        context: dict[str, Any] | None = None,
    ) -> None: ...

    def log_sensitive_access(
        self,
        *,
        reservation_code: str,
        actor: str,
        accessed_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> None: ...


class UpdateReservationStatusUseCase:
    """Update reservation lifecycle state from payment/provider responses.

    Example:
        ```python
        request = UpdateReservationStatusRequest(...)
        status = await use_case.execute(request)
        ```
    """

    def __init__(
        self,
        status_store: ReservationStatusStore,
        audit_logger: UpdateReservationAuditLogger | None = None,
    ) -> None:
        self._status_store = status_store
        self._audit_logger = audit_logger

    async def execute(self, request: UpdateReservationStatusRequest) -> ReservationStatus:
        """Persist external response and update reservation status."""
        current_status = await self._status_store.get_status(request.reservation_code)
        responded_at = request.responded_at or datetime.now(UTC)
        await self._status_store.save_external_response(
            reservation_code=request.reservation_code,
            provider_code=request.provider_code,
            request_type=request.request_type,
            success=request.success,
            request_payload=request.request_payload,
            response_payload=request.response_payload,
            responded_at=responded_at,
        )
        if self._audit_logger is not None:
            self._audit_logger.log_sensitive_access(
                reservation_code=request.reservation_code.value,
                actor="system",
                accessed_data={
                    "request_payload": dict(request.request_payload or {}),
                    "response_payload": dict(request.response_payload or {}),
                },
                context={
                    "provider_code": request.provider_code,
                    "request_type": request.request_type,
                    "success": request.success,
                },
            )

        payment_success = (
            request.success
            if request.request_type == "PAYMENT"
            else await self._status_store.has_successful_request(request.reservation_code, "PAYMENT")
        )
        provider_success = (
            request.success
            if request.request_type == "BOOKING"
            else await self._status_store.has_successful_request(request.reservation_code, "BOOKING")
        )

        target_status = self._resolve_status(
            current_status=current_status,
            payment_success=payment_success,
            provider_success=provider_success,
        )
        if target_status != current_status:
            await self._status_store.set_status(
                reservation_code=request.reservation_code,
                from_status=current_status,
                status=target_status,
                changed_at=responded_at,
            )
            if self._audit_logger is not None:
                self._audit_logger.log_reservation_modified(
                    reservation_code=request.reservation_code.value,
                    actor="system",
                    context={
                        "from_status": current_status.value,
                        "to_status": target_status.value,
                        "provider_code": request.provider_code,
                        "request_type": request.request_type,
                        "success": request.success,
                    },
                )
        return target_status

    @staticmethod
    def _resolve_status(
        *,
        current_status: ReservationStatus,
        payment_success: bool,
        provider_success: bool,
    ) -> ReservationStatus:
        """Resolve lifecycle status from success flags and current state."""
        if current_status == ReservationStatus.CANCELLED:
            return current_status
        if payment_success and provider_success:
            return ReservationStatus.SUPPLIER_CONFIRMED
        if payment_success:
            return ReservationStatus.PAID
        return ReservationStatus.CREATED
