import logging
from datetime import datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from reservas_api.shared.logging import AuditLogger


class _AuditCaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.events: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        if hasattr(record, "audit_event"):
            self.events.append(record.audit_event)


def _build_captured_audit_logger() -> tuple[AuditLogger, _AuditCaptureHandler, logging.Logger]:
    logger = logging.getLogger("reservas_api.audit.properties")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = _AuditCaptureHandler()
    logger.handlers.clear()
    logger.addHandler(handler)
    return AuditLogger(logger=logger), handler, logger


@settings(max_examples=20, deadline=None)
@given(
    reservation_code=st.text(
        alphabet=st.characters(min_codepoint=48, max_codepoint=122).filter(str.isalnum),
        min_size=8,
        max_size=8,
    ),
    supplier_code=st.text(
        alphabet=st.characters(min_codepoint=48, max_codepoint=122).filter(str.isalnum),
        min_size=3,
        max_size=8,
    ),
)
def test_property_23_audit_changes_include_metadata(
    reservation_code: str,
    supplier_code: str,
) -> None:
    """
    Feature: reservas-api, Property 23: Auditoria de cambios con metadata
    Validates: Requirements 13.1
    """
    logger, handler, raw_logger = _build_captured_audit_logger()
    try:
        logger.log_reservation_modified(
            reservation_code=reservation_code,
            actor="system",
            context={"supplier_code": supplier_code, "reason": "status_update"},
        )

        events = handler.events
        assert len(events) == 1
        event = events[0]
        parsed_timestamp = datetime.fromisoformat(event["timestamp"])
        assert parsed_timestamp.tzinfo is not None
        assert event["action"] == "RESERVATION_MODIFIED"
        assert event["reservation_code"] == reservation_code
        assert event["actor"] == "system"
        assert event["context"]["supplier_code"] == supplier_code
        assert event["context"]["reason"] == "status_update"
    finally:
        raw_logger.handlers.clear()


@settings(max_examples=20, deadline=None)
@given(
    reservation_code=st.text(
        alphabet=st.characters(min_codepoint=48, max_codepoint=122).filter(str.isalnum),
        min_size=8,
        max_size=8,
    ),
    email_local=st.text(
        alphabet=st.characters(min_codepoint=97, max_codepoint=122),
        min_size=3,
        max_size=8,
    ),
)
def test_property_24_sensitive_access_is_audited(
    reservation_code: str,
    email_local: str,
) -> None:
    """
    Feature: reservas-api, Property 24: Logs de auditoria para acceso a datos sensibles
    Validates: Requirements 13.2
    """
    logger, handler, raw_logger = _build_captured_audit_logger()
    raw_email = f"{email_local}@example.com"

    try:
        logger.log_sensitive_access(
            reservation_code=reservation_code,
            actor="worker",
            accessed_data={
                "email": raw_email,
                "card_number": "4111111111111111",
                "token": "tok_secret_value",
            },
            context={"reason": "payment_callback"},
        )

        events = handler.events
        assert len(events) == 1
        event = events[0]
        assert event["action"] == "SENSITIVE_ACCESS"
        assert event["reservation_code"] == reservation_code
        assert event["actor"] == "worker"
        assert event["context"]["reason"] == "payment_callback"
        assert event["context"]["data"]["email"] != raw_email
        assert event["context"]["data"]["card_number"] == "***MASKED***"
        assert event["context"]["data"]["token"] == "***MASKED***"
    finally:
        raw_logger.handlers.clear()


@settings(max_examples=20, deadline=None)
@given(
    email_local=st.text(
        alphabet=st.characters(min_codepoint=97, max_codepoint=122),
        min_size=3,
        max_size=10,
    ),
    phone_digits=st.text(
        alphabet=st.characters(min_codepoint=48, max_codepoint=57),
        min_size=7,
        max_size=12,
    ),
)
def test_property_27_sensitive_data_is_masked_in_logs(
    email_local: str,
    phone_digits: str,
) -> None:
    """
    Feature: reservas-api, Property 27: Enmascaramiento de datos sensibles en logs
    Validates: Requirements 14.3
    """
    raw_payload = {
        "customer_email": f"{email_local}@example.com",
        "customer_phone": phone_digits,
        "card_number": "5555444433332222",
        "cvv": "123",
        "metadata": {"api_token": "super-secret-token"},
    }

    masked = AuditLogger.mask_sensitive_data(raw_payload)

    assert masked["customer_email"] != raw_payload["customer_email"]
    assert masked["customer_phone"] != raw_payload["customer_phone"]
    assert masked["card_number"] == "***MASKED***"
    assert masked["cvv"] == "***MASKED***"
    assert masked["metadata"]["api_token"] == "***MASKED***"
