from datetime import UTC

import httpx

from reservas_api.domain.entities import Reservation
from reservas_api.domain.ports import PaymentResult
from reservas_api.infrastructure.resilience import CircuitBreaker, CircuitBreakerOpenError


class StripePaymentGateway:
    def __init__(
        self,
        client: httpx.AsyncClient,
        circuit_breaker: CircuitBreaker,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._client = client
        self._circuit_breaker = circuit_breaker
        self._timeout_seconds = timeout_seconds

    async def process_payment(self, reservation: Reservation) -> PaymentResult:
        async def _request() -> PaymentResult:
            response = await self._client.post(
                "/payments",
                json=self._build_payment_payload(reservation),
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            status = str(payload.get("status", "SUCCESS")).upper()
            return PaymentResult(success=True, status=status, payload=payload)

        try:
            return await self._circuit_breaker.call(_request)
        except CircuitBreakerOpenError:
            return PaymentResult(success=False, status="CIRCUIT_OPEN", payload=None)
        except httpx.TimeoutException:
            return PaymentResult(success=False, status="TIMEOUT", payload=None)
        except httpx.HTTPError as exc:
            return PaymentResult(
                success=False,
                status="FAILED",
                payload={"error": str(exc)},
            )

    @staticmethod
    def _build_payment_payload(reservation: Reservation) -> dict:
        pickup = reservation.pickup_datetime.astimezone(UTC).isoformat()
        dropoff = reservation.dropoff_datetime.astimezone(UTC).isoformat()
        return {
            "reservation_code": reservation.reservation_code.value,
            "amount": str(reservation.total_amount),
            "currency": "EUR",
            "supplier_code": reservation.supplier_code,
            "pickup_datetime": pickup,
            "dropoff_datetime": dropoff,
            "customer": reservation.customer_snapshot,
            "vehicle": reservation.vehicle_snapshot,
        }

