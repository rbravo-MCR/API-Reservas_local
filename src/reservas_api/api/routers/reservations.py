from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from reservas_api.api.schemas import ErrorResponseDTO, ReservationRequestDTO, ReservationResponseDTO
from reservas_api.application import (
    CreateReservationRequest,
    CreateReservationUseCase,
    GenerateReservationCodeUseCase,
)
from reservas_api.infrastructure.outbox import OutboxEventPublisher
from reservas_api.infrastructure.repositories import MySQLReservationRepository

router = APIRouter(prefix="/reservations", tags=["reservations"])

CreateReservationUseCaseFactory = Callable[[], CreateReservationUseCase]


def _build_default_create_reservation_use_case_factory(
    request: Request,
) -> CreateReservationUseCaseFactory:
    """Build default use-case factory from app container/session resources."""
    session_factory = request.app.state.session_factory

    def _factory() -> CreateReservationUseCase:
        repository = MySQLReservationRepository(session_factory)
        generate_code_use_case = GenerateReservationCodeUseCase(repository=repository)
        outbox_writer = OutboxEventPublisher(session_factory)
        return CreateReservationUseCase(
            generate_code_use_case=generate_code_use_case,
            outbox_writer=outbox_writer,
        )

    return _factory


def get_create_reservation_use_case(request: Request) -> CreateReservationUseCase:
    """Resolve create-reservation use case via app state or default wiring."""
    factory: CreateReservationUseCaseFactory | None = getattr(
        request.app.state,
        "create_reservation_use_case_factory",
        None,
    )
    if factory is None:
        factory = _build_default_create_reservation_use_case_factory(request)
    return factory()


@router.post(
    "",
    response_model=ReservationResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create reservation",
    description="Create a reservation and enqueue external processing via outbox.",
    responses={
        201: {
            "description": "Reservation created",
            "content": {
                "application/json": {
                    "example": {
                        "reservation_code": "AB12CD34",
                        "status": "CREATED",
                        "supplier_code": "SUP01",
                        "pickup_datetime": "2026-12-01T10:00:00Z",
                        "dropoff_datetime": "2026-12-03T10:00:00Z",
                        "total_amount": "180.50",
                        "created_at": "2026-12-01T09:59:58Z",
                    }
                }
            },
        },
        400: {
            "model": ErrorResponseDTO,
            "description": "Business rule violation",
        },
        422: {
            "model": ErrorResponseDTO,
            "description": "Validation error",
        },
        429: {
            "model": ErrorResponseDTO,
            "description": "Rate limit exceeded",
        },
        500: {
            "model": ErrorResponseDTO,
            "description": "Internal server/database error",
        },
    },
)
async def create_reservation(
    payload: ReservationRequestDTO,
    use_case: Annotated[CreateReservationUseCase, Depends(get_create_reservation_use_case)],
) -> ReservationResponseDTO:
    """Create and persist a reservation from validated API input."""
    request_model = CreateReservationRequest(
        supplier_code=payload.supplier_code,
        pickup_office_code=payload.pickup_office_code,
        dropoff_office_code=payload.dropoff_office_code,
        pickup_datetime=payload.pickup_datetime,
        dropoff_datetime=payload.dropoff_datetime,
        total_amount=payload.total_amount,
        customer=payload.customer.model_dump(mode="json"),
        vehicle=payload.vehicle.model_dump(mode="json"),
    )
    reservation = await use_case.execute(request_model)
    return ReservationResponseDTO(
        reservation_code=reservation.reservation_code.value,
        status=reservation.status,
        supplier_code=reservation.supplier_code,
        pickup_datetime=reservation.pickup_datetime,
        dropoff_datetime=reservation.dropoff_datetime,
        total_amount=reservation.total_amount,
        created_at=reservation.created_at,
    )
