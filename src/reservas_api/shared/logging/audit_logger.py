import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any


class AuditLogger:
    """Structured audit logger with automatic sensitive-data masking.

    Example:
        ```python
        audit = AuditLogger()
        audit.log_reservation_created(reservation_code="AB12CD34", actor="system")
        ```
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._logger = logger or logging.getLogger("reservas_api.audit")
        self._clock = clock or (lambda: datetime.now(UTC))

    def log_reservation_created(
        self,
        *,
        reservation_code: str,
        actor: str,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        """Emit reservation creation audit event."""
        self._emit(
            action="RESERVATION_CREATED",
            reservation_code=reservation_code,
            actor=actor,
            context=context or {},
        )

    def log_reservation_modified(
        self,
        *,
        reservation_code: str,
        actor: str,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        """Emit reservation modification audit event."""
        self._emit(
            action="RESERVATION_MODIFIED",
            reservation_code=reservation_code,
            actor=actor,
            context=context or {},
        )

    def log_sensitive_access(
        self,
        *,
        reservation_code: str,
        actor: str,
        accessed_data: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> None:
        """Emit sensitive-data access audit event with masked payload."""
        base_context = dict(context or {})
        base_context["data"] = self.mask_sensitive_data(dict(accessed_data))
        self._emit(
            action="SENSITIVE_ACCESS",
            reservation_code=reservation_code,
            actor=actor,
            context=base_context,
        )

    def _emit(
        self,
        *,
        action: str,
        reservation_code: str,
        actor: str,
        context: Mapping[str, Any],
    ) -> None:
        event = {
            "timestamp": self._clock().astimezone(UTC).isoformat(),
            "action": action,
            "reservation_code": reservation_code,
            "actor": actor,
            "context": self.mask_sensitive_data(dict(context)),
        }
        self._logger.info("audit_event", extra={"audit_event": event})

    @classmethod
    def mask_sensitive_data(cls, value: Any, key: str | None = None) -> Any:
        """Recursively mask sensitive values based on key names."""
        if isinstance(value, dict):
            return {k: cls.mask_sensitive_data(v, key=k) for k, v in value.items()}
        if isinstance(value, list):
            return [cls.mask_sensitive_data(item, key=key) for item in value]
        if isinstance(value, tuple):
            return tuple(cls.mask_sensitive_data(item, key=key) for item in value)
        if isinstance(value, str) and cls._is_sensitive_key(key):
            return cls._mask_string(value, key or "")
        return value

    @staticmethod
    def _is_sensitive_key(key: str | None) -> bool:
        if not key:
            return False
        lowered = key.lower()
        sensitive_tokens = (
            "email",
            "phone",
            "card",
            "cvv",
            "token",
            "password",
            "secret",
        )
        return any(token in lowered for token in sensitive_tokens)

    @staticmethod
    def _mask_string(raw: str, key: str) -> str:
        lowered_key = key.lower()
        if "email" in lowered_key:
            local_part, _, domain = raw.partition("@")
            if not domain:
                return "***"
            prefix = (local_part[:1] or "*")
            return f"{prefix}***@{domain}"
        if "phone" in lowered_key:
            digits = "".join(ch for ch in raw if ch.isdigit())
            if len(digits) <= 2:
                return "***"
            return f"{'*' * (len(digits) - 2)}{digits[-2:]}"
        return "***MASKED***"
