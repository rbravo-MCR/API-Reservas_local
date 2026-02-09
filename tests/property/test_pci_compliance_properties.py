import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from reservas_api.shared.security.pci import enforce_pci_storage_rules


@settings(max_examples=30, deadline=None)
@given(card_number=st.text(alphabet=st.characters(min_codepoint=48, max_codepoint=57), min_size=12, max_size=19))
def test_property_26_rejects_plain_card_numbers(card_number: str) -> None:
    """
    Feature: reservas-api, Property 26: No almacenar datos de tarjeta sin tokenizar
    Validates: Requirements 14.2
    """
    payload = {
        "payment": {
            "card_number": card_number,
            "cvv": "123",
        }
    }

    with pytest.raises(ValueError, match="Card number must be tokenized"):
        enforce_pci_storage_rules(payload)


@settings(max_examples=30, deadline=None)
@given(
    token_suffix=st.text(
        alphabet=st.characters(min_codepoint=48, max_codepoint=122).filter(str.isalnum),
        min_size=8,
        max_size=24,
    )
)
def test_property_26_allows_tokenized_values_and_removes_cvv(token_suffix: str) -> None:
    """
    Feature: reservas-api, Property 26: No almacenar datos de tarjeta sin tokenizar
    Validates: Requirements 14.2
    """
    payload = {
        "payment": {
            "card_token": f"tok_{token_suffix}",
            "cvv": "999",
            "holder": "Ana Perez",
        }
    }

    sanitized = enforce_pci_storage_rules(payload)

    assert sanitized["payment"]["card_token"] == payload["payment"]["card_token"]
    assert "cvv" not in sanitized["payment"]
    assert sanitized["payment"]["holder"] == "Ana Perez"
