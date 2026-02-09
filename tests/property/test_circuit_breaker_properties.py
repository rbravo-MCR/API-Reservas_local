import asyncio

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from reservas_api.infrastructure.resilience import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
)


@settings(max_examples=50, deadline=None)
@given(failure_threshold=st.integers(min_value=1, max_value=20))
def test_property_20_circuit_breaker_opens_after_repeated_failures(
    failure_threshold: int,
) -> None:
    """
    Feature: reservas-api, Property 20: Circuit breaker abre despues de fallos repetidos
    Validates: Requirements 10.5
    """
    breaker = CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout_seconds=60.0,
    )
    executions = 0

    async def failing_call() -> None:
        nonlocal executions
        executions += 1
        raise RuntimeError("external service failed")

    async def run_scenario() -> None:
        for _ in range(failure_threshold):
            with pytest.raises(RuntimeError):
                await breaker.call(failing_call)

        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == failure_threshold

        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(failing_call)

    asyncio.run(run_scenario())
    assert executions == failure_threshold

