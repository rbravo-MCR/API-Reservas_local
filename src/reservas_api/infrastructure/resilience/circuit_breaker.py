import asyncio
from collections.abc import Awaitable, Callable
from enum import StrEnum
from time import monotonic
from typing import TypeVar

T = TypeVar("T")


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenError(RuntimeError):
    pass


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
        time_provider: Callable[[], float] | None = None,
    ) -> None:
        if failure_threshold <= 0:
            raise ValueError("failure_threshold must be greater than zero")
        if recovery_timeout_seconds <= 0:
            raise ValueError("recovery_timeout_seconds must be greater than zero")

        self._failure_threshold = failure_threshold
        self._recovery_timeout_seconds = recovery_timeout_seconds
        self._time_provider = time_provider or monotonic

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    async def call(self, func: Callable[[], Awaitable[T]]) -> T:
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                else:
                    raise CircuitBreakerOpenError("Circuit breaker is OPEN")

        try:
            result = await func()
        except Exception:
            async with self._lock:
                self._on_failure()
            raise
        else:
            async with self._lock:
                self._on_success()
            return result

    def _should_attempt_reset(self) -> bool:
        if self._opened_at is None:
            return False
        return (self._time_provider() - self._opened_at) >= self._recovery_timeout_seconds

    def _on_success(self) -> None:
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        self._opened_at = None

    def _on_failure(self) -> None:
        self._failure_count += 1
        if self._state == CircuitState.HALF_OPEN or self._failure_count >= self._failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = self._time_provider()

