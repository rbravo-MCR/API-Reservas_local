from collections import deque

import pytest

from reservas_api.infrastructure.resilience import RetryPolicy


@pytest.mark.asyncio
async def test_retry_policy_uses_exponential_backoff_until_success() -> None:
    delays: list[float] = []
    outcomes = deque([RuntimeError("first"), RuntimeError("second"), "ok"])

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    async def flaky_call() -> str:
        result = outcomes.popleft()
        if isinstance(result, Exception):
            raise result
        return result

    policy = RetryPolicy(
        max_retries=3,
        base_delay_seconds=1.0,
        backoff_factor=2.0,
        max_delay_seconds=10.0,
        sleep_func=fake_sleep,
    )

    value = await policy.execute(flaky_call)

    assert value == "ok"
    assert delays == [1.0, 2.0]


@pytest.mark.asyncio
async def test_retry_policy_raises_after_max_retries() -> None:
    attempts = 0
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    async def always_fail() -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("fail")

    policy = RetryPolicy(
        max_retries=2,
        base_delay_seconds=0.5,
        backoff_factor=2.0,
        max_delay_seconds=10.0,
        sleep_func=fake_sleep,
    )

    with pytest.raises(RuntimeError, match="fail"):
        await policy.execute(always_fail)

    assert attempts == 3
    assert delays == [0.5, 1.0]

