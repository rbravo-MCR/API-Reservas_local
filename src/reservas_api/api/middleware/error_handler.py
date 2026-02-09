import logging
import re
from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware

from reservas_api.api.schemas import ErrorResponseDTO
from reservas_api.application import (
    CreateReservationPersistenceError,
    ReservationCodeGenerationError,
    ReservationStatusUpdateNotFoundError,
)

logger = logging.getLogger(__name__)


def _mask_sensitive(text: str) -> str:
    masked = re.sub(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})", r"\1***@\2", text)
    masked = re.sub(r"\b\d{12,19}\b", "****MASKED_CARD****", masked)
    masked = re.sub(r"(?i)(cvv|password|token|secret)\s*[:=]\s*[^,\s]+", r"\1=***", masked)
    return masked


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            return await call_next(request)
        except RequestValidationError as exc:
            self._log_exception("validation_error", request, exc)
            return JSONResponse(
                status_code=422,
                content=build_validation_error_response().model_dump(),
            )
        except (
            ReservationCodeGenerationError,
            ReservationStatusUpdateNotFoundError,
            ValueError,
        ) as exc:
            self._log_exception("business_error", request, exc)
            return JSONResponse(
                status_code=400,
                content=ErrorResponseDTO(
                    error="Bad request",
                    message="Business rule validation failed",
                    code="BUSINESS_LOGIC_ERROR",
                ).model_dump(),
            )
        except (CreateReservationPersistenceError, SQLAlchemyError) as exc:
            self._log_exception("database_error", request, exc)
            return JSONResponse(
                status_code=500,
                content=ErrorResponseDTO(
                    error="Internal server error",
                    message="Unable to process request. Please try again later.",
                    code="DATABASE_ERROR",
                ).model_dump(),
            )
        except Exception as exc:
            self._log_exception("unexpected_error", request, exc)
            return JSONResponse(
                status_code=500,
                content=ErrorResponseDTO(
                    error="Internal server error",
                    message="Unable to process request. Please try again later.",
                    code="INTERNAL_ERROR",
                ).model_dump(),
            )

    @staticmethod
    def _log_exception(error_type: str, request: Request, exc: Exception) -> None:
        logger.exception(
            "api_error type=%s method=%s path=%s detail=%s",
            error_type,
            request.method,
            request.url.path,
            _mask_sensitive(str(exc)),
        )


def build_validation_error_response() -> ErrorResponseDTO:
    return ErrorResponseDTO(
        error="Validation error",
        message="Request validation failed",
        code="VALIDATION_ERROR",
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    ErrorHandlerMiddleware._log_exception("validation_error", request, exc)
    return JSONResponse(
        status_code=422,
        content=build_validation_error_response().model_dump(),
    )
