import re
from typing import Any

CARD_NUMBER_PATTERN = re.compile(r"^\d{12,19}$")
TOKEN_PATTERN = re.compile(r"^(tok_|pm_|card_)[A-Za-z0-9_]+$")


def enforce_pci_storage_rules(payload: Any) -> Any:
    """Reject PAN/CVV persistence and keep only token-safe payment data.

    Example:
        ```python
        safe = enforce_pci_storage_rules({"card_token": "tok_abc123"})
        ```
    """
    if isinstance(payload, dict):
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            lowered_key = key.lower()
            if lowered_key in {"cvv", "cvc", "security_code"}:
                continue

            if _looks_like_card_number_field(lowered_key):
                value_str = str(value).strip()
                if CARD_NUMBER_PATTERN.fullmatch(value_str):
                    raise ValueError("Card number must be tokenized before persistence")
                if _looks_like_token_field(lowered_key) and not TOKEN_PATTERN.fullmatch(value_str):
                    raise ValueError("Card token format is invalid")
                sanitized[key] = value
                continue

            sanitized[key] = enforce_pci_storage_rules(value)
        return sanitized
    if isinstance(payload, list):
        return [enforce_pci_storage_rules(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(enforce_pci_storage_rules(item) for item in payload)
    return payload


def _looks_like_card_number_field(key: str) -> bool:
    tokens = ("card", "pan", "account_number")
    return any(token in key for token in tokens)


def _looks_like_token_field(key: str) -> bool:
    return "token" in key
