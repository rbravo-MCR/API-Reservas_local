from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from reservas_api.domain.entities import Reservation, ReservationAddon
from reservas_api.domain.enums import ReservationStatus
from reservas_api.domain.value_objects import ReservationCode
from reservas_api.infrastructure.db.models import ReservationAddonModel, ReservationModel


class ReservationNotFoundError(ValueError):
    pass


class MySQLReservationRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(
        self,
        reservation: Reservation,
        session: AsyncSession | None = None,
    ) -> Reservation:
        if session is not None:
            return await self._save_with_session(session, reservation)

        async with self._session_factory() as db_session:
            async with db_session.begin():
                return await self._save_with_session(db_session, reservation)

    async def find_by_code(self, code: ReservationCode) -> Reservation | None:
        async with self._session_factory() as session:
            result = await session.exec(
                select(ReservationModel).where(ReservationModel.reservation_code == code.value)
            )
            model = result.one_or_none()
            if model is None:
                return None
            addon_result = await session.exec(
                select(ReservationAddonModel).where(
                    ReservationAddonModel.reservation_code == code.value
                )
            )
            addon_models = addon_result.all()
            reservation = self._to_domain(model)
            reservation.addons = [
                ReservationAddon(
                    addon_code=a.addon_code,
                    addon_name_snapshot=a.addon_name_snapshot,
                    addon_category_snapshot=a.addon_category_snapshot,
                    quantity=a.quantity,
                    unit_price=a.unit_price,
                    total_price=a.total_price,
                    currency_code=a.currency_code,
                )
                for a in addon_models
            ]
            return reservation

    async def exists_code(self, code: ReservationCode) -> bool:
        async with self._session_factory() as session:
            query = select(func.count(ReservationModel.id)).where(
                ReservationModel.reservation_code == code.value
            )
            result = await session.exec(query)
            return int(result.one()) > 0

    async def update_status(self, code: ReservationCode, status: ReservationStatus) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.exec(
                    select(ReservationModel).where(ReservationModel.reservation_code == code.value)
                )
                model = result.one_or_none()
                if model is None:
                    raise ReservationNotFoundError(f"Reservation not found for code={code.value}")
                model.status = status

    async def _save_with_session(
        self,
        session: AsyncSession,
        reservation: Reservation,
    ) -> Reservation:
        if reservation.id is None:
            model = self._to_model(reservation)
            session.add(model)
            await session.flush()
            return self._to_domain(model)

        existing = await session.exec(
            select(ReservationModel).where(
                ReservationModel.reservation_code == reservation.reservation_code.value
            )
        )
        model = existing.one_or_none()
        if model is None:
            model = self._to_model(reservation)
            session.add(model)
        else:
            self._update_model(model, reservation)

        await session.flush()
        return self._to_domain(model)

    @staticmethod
    def _to_model(reservation: Reservation) -> ReservationModel:
        return ReservationModel(
            id=reservation.id,
            reservation_code=reservation.reservation_code.value,
            status=reservation.status,
            supplier_code=reservation.supplier_code,
            pickup_office_code=reservation.pickup_office_code,
            dropoff_office_code=reservation.dropoff_office_code,
            pickup_datetime=reservation.pickup_datetime,
            dropoff_datetime=reservation.dropoff_datetime,
            total_amount=reservation.total_amount,
            customer_snapshot=reservation.customer_snapshot,
            vehicle_snapshot=reservation.vehicle_snapshot,
            created_at=reservation.created_at,
        )

    @staticmethod
    def _update_model(model: ReservationModel, reservation: Reservation) -> None:
        model.status = reservation.status
        model.supplier_code = reservation.supplier_code
        model.pickup_office_code = reservation.pickup_office_code
        model.dropoff_office_code = reservation.dropoff_office_code
        model.pickup_datetime = reservation.pickup_datetime
        model.dropoff_datetime = reservation.dropoff_datetime
        model.total_amount = reservation.total_amount
        model.customer_snapshot = reservation.customer_snapshot
        model.vehicle_snapshot = reservation.vehicle_snapshot

    @staticmethod
    def _to_domain(model: ReservationModel) -> Reservation:
        return Reservation(
            id=model.id,
            reservation_code=ReservationCode(model.reservation_code),
            status=model.status,
            supplier_code=model.supplier_code,
            pickup_office_code=model.pickup_office_code,
            dropoff_office_code=model.dropoff_office_code,
            pickup_datetime=model.pickup_datetime,
            dropoff_datetime=model.dropoff_datetime,
            total_amount=model.total_amount or Decimal("0.00"),
            customer_snapshot=model.customer_snapshot or {},
            vehicle_snapshot=model.vehicle_snapshot or {},
            created_at=model.created_at or datetime.now(UTC),
        )
