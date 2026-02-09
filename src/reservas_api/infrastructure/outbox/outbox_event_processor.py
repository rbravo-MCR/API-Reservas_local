import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from reservas_api.domain.entities import Reservation
from reservas_api.domain.ports import PaymentGateway, ProviderGateway
from reservas_api.domain.value_objects import ReservationCode
from reservas_api.infrastructure.db.models import ProviderOutboxEventModel


class OutboxEventProcessor:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        payment_gateway: PaymentGateway,
        provider_gateway: ProviderGateway,
        poll_interval_seconds: float = 5.0,
        batch_size: int = 20,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be greater than zero")
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")

        self._session_factory = session_factory
        self._payment_gateway = payment_gateway
        self._provider_gateway = provider_gateway
        self._poll_interval_seconds = poll_interval_seconds
        self._batch_size = batch_size
        self._stop_event = asyncio.Event()

    async def run_forever(self) -> None:
        while not self._stop_event.is_set():
            await self.process_pending_once(self._batch_size)
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._poll_interval_seconds,
                )
            except TimeoutError:
                continue

    def stop(self) -> None:
        self._stop_event.set()

    async def process_pending_once(self, limit: int | None = None) -> int:
        target_limit = limit if limit is not None else self._batch_size
        async with self._session_factory() as session:
            query = (
                select(ProviderOutboxEventModel.id)
                .where(ProviderOutboxEventModel.status.in_(["PENDING", "FAILED"]))
                .order_by(ProviderOutboxEventModel.id)
                .limit(target_limit)
            )
            result = await session.exec(query)
            event_ids = list(result.all())

        processed = 0
        for event_id in event_ids:
            if await self._process_event_by_id(event_id):
                processed += 1
        return processed

    async def _process_event_by_id(self, event_id: int) -> bool:
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.exec(
                    select(ProviderOutboxEventModel).where(ProviderOutboxEventModel.id == event_id)
                )
                event = result.one_or_none()
                if event is None or event.status == "PROCESSED":
                    return False
                try:
                    await self._dispatch_event(event)
                    event.status = "PROCESSED"
                    payload = dict(event.payload or {})
                    payload.pop("last_error", None)
                    event.payload = payload
                    return True
                except Exception as exc:
                    event.status = "FAILED"
                    payload = dict(event.payload or {})
                    payload["last_error"] = str(exc)
                    event.payload = payload
                    return False

    async def _dispatch_event(self, event: ProviderOutboxEventModel) -> None:
        reservation = self._reservation_from_payload(
            reservation_code=event.aggregate_id,
            payload=dict(event.payload or {}),
        )
        if event.event_type == "PAYMENT_REQUESTED":
            await self._payment_gateway.process_payment(reservation)
            return
        if event.event_type == "BOOKING_REQUESTED":
            await self._provider_gateway.create_booking(reservation)
            return
        raise ValueError(f"Unsupported outbox event type: {event.event_type}")

    @staticmethod
    def _reservation_from_payload(reservation_code: str, payload: dict) -> Reservation:
        reservation_payload = dict(payload.get("reservation") or {})
        pickup = OutboxEventProcessor._parse_datetime(
            reservation_payload.get("pickup_datetime"),
            fallback=datetime.now(UTC),
        )
        dropoff = OutboxEventProcessor._parse_datetime(
            reservation_payload.get("dropoff_datetime"),
            fallback=pickup + timedelta(hours=1),
        )
        total_amount = OutboxEventProcessor._parse_decimal(
            reservation_payload.get("total_amount"),
            fallback=Decimal("1.00"),
        )
        return Reservation(
            reservation_code=ReservationCode(reservation_code),
            supplier_code=str(reservation_payload.get("supplier_code") or "UNKNOWN"),
            pickup_office_code=str(reservation_payload.get("pickup_office_code") or "UNKNOWN"),
            dropoff_office_code=str(reservation_payload.get("dropoff_office_code") or "UNKNOWN"),
            pickup_datetime=pickup,
            dropoff_datetime=dropoff,
            total_amount=total_amount,
            customer_snapshot=dict(reservation_payload.get("customer_snapshot") or {}),
            vehicle_snapshot=dict(reservation_payload.get("vehicle_snapshot") or {}),
        )

    @staticmethod
    def _parse_datetime(raw_value: object, fallback: datetime) -> datetime:
        if isinstance(raw_value, datetime):
            value = raw_value
        elif isinstance(raw_value, str):
            try:
                value = datetime.fromisoformat(raw_value)
            except ValueError:
                return fallback
        else:
            return fallback

        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    @staticmethod
    def _parse_decimal(raw_value: object, fallback: Decimal) -> Decimal:
        try:
            value = Decimal(str(raw_value))
        except (InvalidOperation, ValueError, TypeError):
            return fallback
        if value <= Decimal("0"):
            return fallback
        return value

