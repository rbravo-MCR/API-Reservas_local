import asyncio
from collections import deque
from threading import Lock

from hypothesis import given, settings
from hypothesis import strategies as st

from reservas_api.application.use_cases import GenerateReservationCodeUseCase
from reservas_api.domain.value_objects import ReservationCode


class AtomicCodeRegistryRepository:
    def __init__(self) -> None:
        self._seen_codes: set[str] = set()
        self._lock = asyncio.Lock()

    async def exists_code(self, code: ReservationCode) -> bool:
        async with self._lock:
            if code.value in self._seen_codes:
                return True
            self._seen_codes.add(code.value)
            return False


class DeterministicCodeGenerator:
    def __init__(self, values: list[str]) -> None:
        self._values = deque(values)
        self._lock = Lock()

    def __call__(self) -> str:
        with self._lock:
            return self._values.popleft()


@settings(max_examples=30, deadline=None)
@given(concurrent_requests=st.integers(min_value=5, max_value=25))
def test_property_22_unique_codes_under_concurrency(concurrent_requests: int) -> None:
    """
    Feature: reservas-api, Property 22: Unicidad de codigos bajo concurrencia
    Validates: Requirements 11.2, 11.5
    """
    repeated_code = "AAAA1111"
    unique_candidates = [f"{value:08X}" for value in range(1, concurrent_requests * 4)]
    generated_values = [repeated_code] * concurrent_requests + unique_candidates

    repository = AtomicCodeRegistryRepository()
    generator = DeterministicCodeGenerator(generated_values)
    use_case = GenerateReservationCodeUseCase(
        repository=repository,
        code_generator=generator,
        max_retries=concurrent_requests * 8,
    )

    async def run_requests() -> list[ReservationCode]:
        tasks = [use_case.execute() for _ in range(concurrent_requests)]
        return await asyncio.gather(*tasks)

    codes = asyncio.run(run_requests())
    values = [item.value for item in codes]

    assert len(values) == concurrent_requests
    assert len(set(values)) == concurrent_requests
    assert all(len(value) == 8 and value.isalnum() for value in values)

