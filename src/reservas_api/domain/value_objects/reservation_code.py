import re
from dataclasses import dataclass

_RESERVATION_CODE_PATTERN = re.compile(r"^[A-Za-z0-9]{8}$")


@dataclass(frozen=True, slots=True)
class ReservationCode:
    """Immutable value object for 8-char alphanumeric reservation codes."""

    value: str

    def __post_init__(self) -> None:
        if not self._is_valid(self.value):
            raise ValueError("Reservation code must be exactly 8 alphanumeric characters")

    @staticmethod
    def _is_valid(value: str) -> bool:
        return bool(_RESERVATION_CODE_PATTERN.fullmatch(value))
