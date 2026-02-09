from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from reservas_api.application.use_cases.update_reservation_status_use_case import (
    ExternalRequestType,
    ReservationStatusUpdateNotFoundError,
)
from reservas_api.domain.enums import ReservationStatus
from reservas_api.domain.value_objects import ReservationCode
from reservas_api.infrastructure.db.models import ReservationModel, ReservationProviderRequestModel
from reservas_api.infrastructure.history import HistoryTracker


class MySQLReservationStatusStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._history_tracker = HistoryTracker(session_factory)

    async def get_status(self, reservation_code: ReservationCode) -> ReservationStatus:
        async with self._session_factory() as session:
            reservation = await self._get_reservation(session, reservation_code)
            return reservation.status

    async def has_successful_request(
        self,
        reservation_code: ReservationCode,
        request_type: ExternalRequestType,
    ) -> bool:
        async with self._session_factory() as session:
            query = select(func.count(ReservationProviderRequestModel.id)).where(
                ReservationProviderRequestModel.reservation_code == reservation_code.value,
                ReservationProviderRequestModel.request_type == request_type,
                ReservationProviderRequestModel.status == "SUCCESS",
            )
            result = await session.exec(query)
            return int(result.one()) > 0

    async def save_external_response(
        self,
        reservation_code: ReservationCode,
        provider_code: str,
        request_type: ExternalRequestType,
        success: bool,
        request_payload: dict[str, Any] | None,
        response_payload: dict[str, Any] | None,
        responded_at: datetime,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                await self._get_reservation(session, reservation_code)
                session.add(
                    ReservationProviderRequestModel(
                        reservation_code=reservation_code.value,
                        provider_code=provider_code,
                        request_type=request_type,
                        request_payload=dict(request_payload or {}),
                        response_payload=dict(response_payload or {}),
                        status="SUCCESS" if success else "FAILED",
                        responded_at=responded_at,
                    )
                )

    async def set_status(
        self,
        reservation_code: ReservationCode,
        from_status: ReservationStatus,
        status: ReservationStatus,
        changed_at: datetime,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                reservation = await self._get_reservation(session, reservation_code)
                reservation.status = status
                await self._history_tracker.track_status_change(
                    session=session,
                    reservation_code=reservation_code.value,
                    from_status=from_status,
                    to_status=status,
                    changed_at=changed_at,
                )

    async def _get_reservation(
        self,
        session: AsyncSession,
        reservation_code: ReservationCode,
    ) -> ReservationModel:
        result = await session.exec(
            select(ReservationModel).where(ReservationModel.reservation_code == reservation_code.value)
        )
        reservation = result.one_or_none()
        if reservation is None:
            raise ReservationStatusUpdateNotFoundError(
                f"Reservation not found for code={reservation_code.value}"
            )
        return reservation
