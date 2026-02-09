from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from reservas_api.domain.entities import Reservation
from reservas_api.domain.value_objects import ReservationCode
from reservas_api.infrastructure.gateways import ProviderAPIGateway
from reservas_api.infrastructure.resilience import CircuitBreaker, RetryPolicy


def _reservation() -> Reservation:
    pickup = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)
    dropoff = pickup + timedelta(days=3)
    return Reservation(
        reservation_code=ReservationCode("ZX98CV76"),
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
async def test_provider_gateway_success_call_returns_success_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/bookings"
        return httpx.Response(200, json={"status": "confirmed", "provider_id": "bk_001"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://provider.test",
    ) as client:
        gateway = ProviderAPIGateway(
            client=client,
            circuit_breaker=CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=60),
            retry_policy=RetryPolicy(max_retries=2, sleep_func=lambda _: _immediate_sleep()),
        )
        result = await gateway.create_booking(_reservation())

    assert result.success is True
    assert result.status == "CONFIRMED"
    assert result.payload == {"status": "confirmed", "provider_id": "bk_001"}


async def _immediate_sleep() -> None:
    return None


@pytest.mark.asyncio
async def test_provider_gateway_retries_and_succeeds_after_transient_failures() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise httpx.ConnectError("connection failed", request=request)
        return httpx.Response(200, json={"status": "confirmed"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://provider.test",
    ) as client:
        gateway = ProviderAPIGateway(
            client=client,
            circuit_breaker=CircuitBreaker(failure_threshold=5, recovery_timeout_seconds=60),
            retry_policy=RetryPolicy(max_retries=3, sleep_func=lambda _: _immediate_sleep()),
        )
        result = await gateway.create_booking(_reservation())

    assert result.success is True
    assert result.status == "CONFIRMED"
    assert attempts == 3


@pytest.mark.asyncio
async def test_provider_gateway_timeout_returns_timeout_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://provider.test",
    ) as client:
        gateway = ProviderAPIGateway(
            client=client,
            circuit_breaker=CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=60),
            retry_policy=RetryPolicy(max_retries=0),
        )
        result = await gateway.create_booking(_reservation())

    assert result.success is False
    assert result.status == "TIMEOUT"


@pytest.mark.asyncio
async def test_provider_gateway_returns_circuit_open_when_breaker_opened() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("connection failed", request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://provider.test",
    ) as client:
        gateway = ProviderAPIGateway(
            client=client,
            circuit_breaker=CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=60),
            retry_policy=RetryPolicy(max_retries=0),
        )

        first = await gateway.create_booking(_reservation())
        second = await gateway.create_booking(_reservation())

    assert first.success is False
    assert first.status == "FAILED"
    assert second.success is False
    assert second.status == "CIRCUIT_OPEN"
    assert attempts == 1

