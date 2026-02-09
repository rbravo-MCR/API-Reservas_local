import secrets
import string
from collections.abc import Callable

from reservas_api.domain.ports import ReservationRepository
from reservas_api.domain.value_objects import ReservationCode

ALPHANUMERIC_CHARS = string.ascii_letters + string.digits


class ReservationCodeGenerationError(RuntimeError):
    """Raised when a unique reservation code cannot be generated."""

    pass


class GenerateReservationCodeUseCase:
    """Generate a unique 8-char alphanumeric reservation code.

    Example:
        ```python
        use_case = GenerateReservationCodeUseCase(repository)
        code = await use_case.execute()
        assert len(code.value) == 8
        ```
    """

    def __init__(
        self,
        repository: ReservationRepository,
        code_generator: Callable[[], str] | None = None,
        max_retries: int = 1_000,
    ) -> None:
        if max_retries <= 0:
            raise ValueError("max_retries must be greater than zero")
        self._repository = repository
        self._code_generator = code_generator or self._generate_random_code
        self._max_retries = max_retries

    async def execute(self) -> ReservationCode:
        """Return a unique reservation code, retrying on collisions."""
        for _ in range(self._max_retries):
            try:
                code = ReservationCode(value=self._code_generator())
            except ValueError:
                continue

            if not await self._repository.exists_code(code):
                return code

        raise ReservationCodeGenerationError(
            "Unable to generate a unique reservation code within max_retries"
        )

    @staticmethod
    def _generate_random_code() -> str:
        """Build a random 8-char alphanumeric code."""
        return "".join(secrets.choice(ALPHANUMERIC_CHARS) for _ in range(8))
