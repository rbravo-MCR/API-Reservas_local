import asyncio
from collections import deque

from hypothesis import given, settings
from hypothesis import strategies as st

from reservas_api.application.use_cases import GenerateReservationCodeUseCase
from reservas_api.domain.value_objects import ReservationCode


class CollisionAwareRepository:
    def __init__(self, existing_codes: set[str]) -> None:
        self._existing_codes = existing_codes
        self.checked_codes: list[str] = []

    async def exists_code(self, code: ReservationCode) -> bool:
        self.checked_codes.append(code.value)
        return code.value in self._existing_codes


@settings(max_examples=100, deadline=None)
@given(collision_attempts=st.integers(min_value=1, max_value=50))
def test_property_3_generation_retries_until_finding_unique_code(collision_attempts: int) -> None:
    """
    Feature: reservas-api, Property 3: Generacion de codigo unico con reintentos
    Validates: Requirements 1.3
    """
    duplicated_code = "AAAA1111"
    unique_code = "BBBB2222"
    outputs = deque([duplicated_code] * collision_attempts + [unique_code])

    repository = CollisionAwareRepository(existing_codes={duplicated_code})
    use_case = GenerateReservationCodeUseCase(
        repository=repository,
        code_generator=lambda: outputs.popleft(),
        max_retries=collision_attempts + 5,
    )

    generated = asyncio.run(use_case.execute())

    assert generated.value == unique_code
    assert repository.checked_codes.count(duplicated_code) == collision_attempts
    assert repository.checked_codes[-1] == unique_code

