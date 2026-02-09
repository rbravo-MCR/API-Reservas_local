import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class RetryPolicy:
    def __init__(
        self,
        max_retries: int = 3,
        base_delay_seconds: float = 0.5,
        backoff_factor: float = 2.0,
        max_delay_seconds: float = 60.0,
        sleep_func: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be greater than or equal to zero")
        if base_delay_seconds <= 0:
            raise ValueError("base_delay_seconds must be greater than zero")
        if backoff_factor < 1:
            raise ValueError("backoff_factor must be greater than or equal to one")
        if max_delay_seconds <= 0:
            raise ValueError("max_delay_seconds must be greater than zero")

        self._max_retries = max_retries
        self._base_delay_seconds = base_delay_seconds
        self._backoff_factor = backoff_factor
        self._max_delay_seconds = max_delay_seconds
        self._sleep_func = sleep_func or asyncio.sleep

    async def execute(self, func: Callable[[], Awaitable[T]]) -> T:
        attempt = 0
        while True:
            try:
                return await func()
            except Exception:
                if attempt >= self._max_retries:
                    raise
                delay = min(
                    self._base_delay_seconds * (self._backoff_factor**attempt),
                    self._max_delay_seconds,
                )
                attempt += 1
                await self._sleep_func(delay)

    async def execute_with_retry(self, func: Callable[[], Awaitable[T]]) -> T:
        return await self.execute(func)

