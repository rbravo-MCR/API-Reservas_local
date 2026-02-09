import re
from typing import Any

XSS_PATTERNS = (
    re.compile(r"(?is)<\s*script[^>]*>.*?<\s*/\s*script\s*>"),
    re.compile(r"(?i)javascript:"),
    re.compile(r"(?i)on\w+\s*="),
)

SQL_INJECTION_PATTERN = re.compile(
    r"(?is)("
    r"--|/\*|\*/|"
    r"\bunion\s+select\b|"
    r"\bdrop\s+table\b|"
    r"\btruncate\s+table\b|"
    r"'\s*(or|and)\s+[\w']+\s*=\s*[\w']+|"
    r";\s*(select|insert|update|delete|drop|alter|truncate|union)\b"
    r")"
)


def sanitize_text(value: str) -> str:
    """Remove XSS-like content and normalize plain text fields."""
    cleaned = value.replace("\x00", "").strip()
    for pattern in XSS_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    cleaned = cleaned.replace("<", "").replace(">", "")
    return cleaned


def validate_text_is_safe(value: str) -> None:
    """Raise error when SQL-injection patterns are detected."""
    if SQL_INJECTION_PATTERN.search(value):
        raise ValueError("Input contains possible SQL injection pattern")


def sanitize_and_validate_text(value: str) -> str:
    """Sanitize and validate a text input in one step.

    Example:
        ```python
        safe = sanitize_and_validate_text("SUP01")
        ```
    """
    cleaned = sanitize_text(value)
    validate_text_is_safe(cleaned)
    return cleaned


def sanitize_and_validate_payload(payload: Any) -> Any:
    """Recursively sanitize/validate all text values from nested payloads."""
    if isinstance(payload, dict):
        return {key: sanitize_and_validate_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [sanitize_and_validate_payload(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(sanitize_and_validate_payload(item) for item in payload)
    if isinstance(payload, str):
        return sanitize_and_validate_text(payload)
    return payload
