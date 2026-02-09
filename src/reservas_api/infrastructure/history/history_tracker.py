from datetime import datetime

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from reservas_api.domain.enums import ReservationStatus
from reservas_api.infrastructure.db.models import ReservationStatusHistoryModel


class HistoryTracker:
    """Persist and read reservation status change history."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def track_status_change(
        self,
        *,
        session: AsyncSession,
        reservation_code: str,
        from_status: ReservationStatus,
        to_status: ReservationStatus,
        changed_at: datetime,
    ) -> None:
        """Store a status transition in the current transaction."""
        session.add(
            ReservationStatusHistoryModel(
                reservation_code=reservation_code,
                from_status=from_status,
                to_status=to_status,
                changed_at=changed_at,
            )
        )

    async def get_history(self, reservation_code: str) -> list[ReservationStatusHistoryModel]:
        """Return ordered status history for a reservation code."""
        async with self._session_factory() as session:
            result = await session.exec(
                select(ReservationStatusHistoryModel)
                .where(ReservationStatusHistoryModel.reservation_code == reservation_code)
                .order_by(ReservationStatusHistoryModel.id)
            )
            return list(result.all())
