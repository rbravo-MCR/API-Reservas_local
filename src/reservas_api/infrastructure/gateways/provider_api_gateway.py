from datetime import UTC

import httpx

from reservas_api.domain.entities import Reservation
from reservas_api.domain.ports import ProviderResult
from reservas_api.infrastructure.resilience import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    RetryPolicy,
)


class ProviderAPIGateway:
    def __init__(
        self,
        client: httpx.AsyncClient,
        circuit_breaker: CircuitBreaker,
        retry_policy: RetryPolicy,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._client = client
        self._circuit_breaker = circuit_breaker
        self._retry_policy = retry_policy
        self._timeout_seconds = timeout_seconds

    async def create_booking(self, reservation: Reservation) -> ProviderResult:
        async def _request() -> ProviderResult:
            response = await self._client.post(
                "/bookings",
                json=self._build_booking_payload(reservation),
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            status = str(payload.get("status", "SUCCESS")).upper()
            return ProviderResult(success=True, status=status, payload=payload)

        async def _request_with_circuit_breaker() -> ProviderResult:
            return await self._circuit_breaker.call(_request)

        try:
            return await self._retry_policy.execute(_request_with_circuit_breaker)
        except CircuitBreakerOpenError:
            return ProviderResult(success=False, status="CIRCUIT_OPEN", payload=None)
        except httpx.TimeoutException:
            return ProviderResult(success=False, status="TIMEOUT", payload=None)
        except httpx.HTTPError as exc:
            return ProviderResult(
                success=False,
                status="FAILED",
                payload={"error": str(exc)},
            )

    @staticmethod
    def _build_booking_payload(reservation: Reservation) -> dict:
        pickup = reservation.pickup_datetime.astimezone(UTC).isoformat()
        dropoff = reservation.dropoff_datetime.astimezone(UTC).isoformat()
        return {
            "reservation_code": reservation.reservation_code.value,
            "supplier_code": reservation.supplier_code,
            "pickup_office_code": reservation.pickup_office_code,
            "dropoff_office_code": reservation.dropoff_office_code,
            "pickup_datetime": pickup,
            "dropoff_datetime": dropoff,
            "customer": reservation.customer_snapshot,
            "vehicle": reservation.vehicle_snapshot,
        }

