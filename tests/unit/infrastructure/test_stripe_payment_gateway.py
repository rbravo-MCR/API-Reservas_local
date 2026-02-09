from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from reservas_api.domain.entities import Reservation
from reservas_api.domain.value_objects import ReservationCode
from reservas_api.infrastructure.gateways import StripePaymentGateway
from reservas_api.infrastructure.resilience import CircuitBreaker


def _reservation() -> Reservation:
    pickup = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)
    dropoff = pickup + timedelta(days=3)
    return Reservation(
        reservation_code=ReservationCode("AB12CD34"),
        supplier_code="SUP001",
        pickup_office_code="MAD01",
        dropoff_office_code="MAD02",
        pickup_datetime=pickup,
        dropoff_datetime=dropoff,
        total_amount=Decimal("250.00"),
        customer_snapshot={"first_name": "Ana", "email": "ana@example.com"},
        vehicle_snapshot={"vehicle_code": "VH001"},
    )


@pytest.mark.asyncio
async def test_stripe_gateway_success_call_returns_success_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/payments"
        return httpx.Response(200, json={"status": "paid", "id": "pay_001"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://stripe.test") as client:
        gateway = StripePaymentGateway(
            client=client,
            circuit_breaker=CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=60),
        )
        result = await gateway.process_payment(_reservation())

    assert result.success is True
    assert result.status == "PAID"
    assert result.payload == {"status": "paid", "id": "pay_001"}


@pytest.mark.asyncio
async def test_stripe_gateway_timeout_returns_timeout_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://stripe.test") as client:
        gateway = StripePaymentGateway(
            client=client,
            circuit_breaker=CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=60),
        )
        result = await gateway.process_payment(_reservation())

    assert result.success is False
    assert result.status == "TIMEOUT"


@pytest.mark.asyncio
async def test_stripe_gateway_returns_circuit_open_when_breaker_opened() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("connection failed", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://stripe.test") as client:
        gateway = StripePaymentGateway(
            client=client,
            circuit_breaker=CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=60),
        )

        first = await gateway.process_payment(_reservation())
        second = await gateway.process_payment(_reservation())

    assert first.success is False
    assert first.status == "FAILED"
    assert second.success is False
    assert second.status == "CIRCUIT_OPEN"
    assert attempts == 1

