from collections.abc import Iterable

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from reservas_api.domain.entities import Reservation
from reservas_api.domain.ports import DomainEvent
from reservas_api.infrastructure.db.models import (
    ProviderOutboxEventModel,
    ReservationAddonModel,
)
from reservas_api.infrastructure.repositories import MySQLReservationRepository


class OutboxEventPublisher:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._reservation_repository = MySQLReservationRepository(session_factory)

    async def publish(self, event: DomainEvent) -> None:
        await self.publish_many([event])

    async def publish_many(self, events: Iterable[DomainEvent]) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                for event in events:
                    session.add(self._to_model(event))

    async def save_reservation_with_outbox(
        self,
        reservation: Reservation,
        events: Iterable[DomainEvent] | None = None,
    ) -> Reservation:
        outbox_events = list(events) if events is not None else self.build_reservation_events(reservation)
        async with self._session_factory() as session:
            async with session.begin():
                saved_reservation = await self._reservation_repository.save(
                    reservation,
                    session=session,
                )
                for addon in reservation.addons:
                    session.add(
                        ReservationAddonModel(
                            reservation_code=saved_reservation.reservation_code.value,
                            addon_code=addon.addon_code,
                            addon_name_snapshot=addon.addon_name_snapshot,
                            addon_category_snapshot=addon.addon_category_snapshot,
                            quantity=addon.quantity,
                            unit_price=addon.unit_price,
                            total_price=addon.total_price,
                            currency_code=addon.currency_code,
                        )
                    )
                for event in outbox_events:
                    session.add(self._to_model(event))
        saved_reservation.addons = list(reservation.addons)
        return saved_reservation

    @staticmethod
    def build_reservation_events(reservation: Reservation) -> list[DomainEvent]:
        addons_payload = [
            {
                "addon_code": addon.addon_code,
                "name": addon.addon_name_snapshot,
                "category": addon.addon_category_snapshot,
                "quantity": addon.quantity,
                "unit_price": str(addon.unit_price),
                "total_price": str(addon.total_price),
                "currency_code": addon.currency_code,
            }
            for addon in reservation.addons
        ]
        payload = {
            "reservation": {
                "reservation_code": reservation.reservation_code.value,
                "supplier_code": reservation.supplier_code,
                "pickup_office_code": reservation.pickup_office_code,
                "dropoff_office_code": reservation.dropoff_office_code,
                "pickup_datetime": reservation.pickup_datetime.isoformat(),
                "dropoff_datetime": reservation.dropoff_datetime.isoformat(),
                "total_amount": str(reservation.total_amount),
                "customer_snapshot": reservation.customer_snapshot,
                "vehicle_snapshot": reservation.vehicle_snapshot,
                "addons": addons_payload,
            }
        }
        return [
            DomainEvent(
                event_type="PAYMENT_REQUESTED",
                aggregate_id=reservation.reservation_code.value,
                payload=payload,
            ),
            DomainEvent(
                event_type="BOOKING_REQUESTED",
                aggregate_id=reservation.reservation_code.value,
                payload=payload,
            ),
        ]

    @staticmethod
    def _to_model(event: DomainEvent) -> ProviderOutboxEventModel:
        payload = dict(event.payload or {})
        return ProviderOutboxEventModel(
            aggregate_id=event.aggregate_id,
            event_type=event.event_type,
            payload=payload,
            status="PENDING",
        )
