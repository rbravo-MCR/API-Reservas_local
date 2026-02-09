import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from reservas_api.shared.security.input_sanitizer import sanitize_and_validate_payload

_SQLI_PATTERNS = {
    "Robert'); DROP TABLE reservations;--",
    "' OR 1=1 --",
    "UNION SELECT password FROM users",
}

_ALL_MALICIOUS_PATTERNS = st.sampled_from(
    [
        "<script>alert('xss')</script>",
        "javascript:alert(1)",
        *_SQLI_PATTERNS,
    ]
)


@settings(max_examples=30, deadline=None)
@given(malicious_fragment=_ALL_MALICIOUS_PATTERNS)
def test_property_28_input_sanitization_prevents_injection(
    malicious_fragment: str,
) -> None:
    """
    Feature: reservas-api, Property 28: Sanitizacion de entradas para prevenir inyeccion
    Validates: Requirements 14.6
    """
    payload = {
        "supplier_code": "SUP01",
        "customer": {
            "first_name": malicious_fragment,
            "email": "ana@example.com",
        },
        "vehicle": {
            "model": malicious_fragment,
            "category": "Economy",
        },
    }

    if malicious_fragment in _SQLI_PATTERNS:
        with pytest.raises(ValueError, match="SQL injection|possible SQL injection"):
            sanitize_and_validate_payload(payload)
        return

    sanitized = sanitize_and_validate_payload(payload)
    serialized = str(sanitized).lower()
    assert "<script" not in serialized
    assert "javascript:" not in serialized
