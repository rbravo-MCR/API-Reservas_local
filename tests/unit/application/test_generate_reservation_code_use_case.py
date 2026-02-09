import pytest

from reservas_api.application.use_cases import (
    GenerateReservationCodeUseCase,
    ReservationCodeGenerationError,
)
from reservas_api.domain.value_objects import ReservationCode


class AlwaysExistsRepository:
    async def exists_code(self, code: ReservationCode) -> bool:
        return True


@pytest.mark.asyncio
async def test_generate_code_raises_when_max_retries_exceeded() -> None:
    use_case = GenerateReservationCodeUseCase(
        repository=AlwaysExistsRepository(),
        code_generator=lambda: "ABCD1234",
        max_retries=3,
    )

    with pytest.raises(ReservationCodeGenerationError):
        await use_case.execute()


def test_generate_code_use_case_rejects_non_positive_max_retries() -> None:
    with pytest.raises(ValueError, match="max_retries must be greater than zero"):
        GenerateReservationCodeUseCase(
            repository=AlwaysExistsRepository(),
            code_generator=lambda: "ABCD1234",
            max_retries=0,
        )

