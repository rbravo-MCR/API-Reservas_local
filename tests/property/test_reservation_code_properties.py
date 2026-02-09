import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from reservas_api.domain.value_objects import ReservationCode


@settings(max_examples=100)
@given(
    st.text(
        alphabet=st.characters(min_codepoint=48, max_codepoint=122).filter(str.isalnum),
        min_size=8,
        max_size=8,
    )
)
def test_property_1_reservation_code_is_exactly_8_alphanumeric(value: str) -> None:
    """
    Feature: reservas-api, Property 1: Codigo de reserva tiene exactamente 8 caracteres alfanumericos
    Validates: Requirements 1.1, 1.4
    """
    code = ReservationCode(value=value)

    assert len(code.value) == 8
    assert code.value.isalnum()


@settings(max_examples=100)
@given(
    st.one_of(
        st.text(min_size=0, max_size=7),
        st.text(min_size=9, max_size=20),
        st.text(
            alphabet=st.characters(
                blacklist_characters="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            ),
            min_size=8,
            max_size=8,
        ),
    )
)
def test_property_1_rejects_invalid_codes(value: str) -> None:
    with pytest.raises(ValueError):
        ReservationCode(value=value)

