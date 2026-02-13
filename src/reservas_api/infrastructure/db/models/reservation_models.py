from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy import Enum as SAEnum
from sqlmodel import Column, Field, SQLModel

from reservas_api.domain.enums import AddonCategory, ReservationStatus


class SupplierModel(SQLModel, table=True):
    __tablename__ = "suppliers"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(sa_column=Column(String(40), nullable=False, unique=True, index=True))
    name: str = Field(sa_column=Column(String(120), nullable=False))
    active: bool = Field(default=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )


class OfficeModel(SQLModel, table=True):
    __tablename__ = "offices"

    id: int | None = Field(default=None, primary_key=True)
    supplier_code: str = Field(
        sa_column=Column(
            String(40),
            ForeignKey("suppliers.code", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    office_code: str = Field(sa_column=Column(String(40), nullable=False, unique=True, index=True))
    name: str = Field(sa_column=Column(String(120), nullable=False))
    city: str = Field(sa_column=Column(String(80), nullable=False))
    country: str = Field(sa_column=Column(String(2), nullable=False))
    active: bool = Field(default=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )


class ReservationModel(SQLModel, table=True):
    __tablename__ = "reservations"

    id: int | None = Field(default=None, primary_key=True)
    reservation_code: str = Field(
        sa_column=Column(String(64), nullable=False, unique=True, index=True)
    )
    status: ReservationStatus = Field(
        sa_column=Column(
            SAEnum(ReservationStatus, name="reservation_status", native_enum=False),
            nullable=False,
            default=ReservationStatus.CREATED,
        )
    )
    supplier_code: str = Field(sa_column=Column(String(40), nullable=False))
    pickup_office_code: str = Field(sa_column=Column(String(40), nullable=False))
    dropoff_office_code: str = Field(sa_column=Column(String(40), nullable=False))
    pickup_datetime: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    dropoff_datetime: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    total_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2)))
    customer_snapshot: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    vehicle_snapshot: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )


class ReservationContactModel(SQLModel, table=True):
    __tablename__ = "reservation_contacts"

    id: int | None = Field(default=None, primary_key=True)
    reservation_code: str = Field(
        sa_column=Column(
            String(64),
            ForeignKey("reservations.reservation_code", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        )
    )
    first_name: str = Field(sa_column=Column(String(100), nullable=False))
    last_name: str = Field(sa_column=Column(String(100), nullable=False))
    email: str = Field(sa_column=Column(String(190), nullable=False))
    phone: str | None = Field(default=None, sa_column=Column(String(40), nullable=True))


class ReservationStatusHistoryModel(SQLModel, table=True):
    __tablename__ = "reservation_status_history"

    id: int | None = Field(default=None, primary_key=True)
    reservation_code: str = Field(
        sa_column=Column(
            String(64),
            ForeignKey("reservations.reservation_code", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    from_status: ReservationStatus = Field(
        sa_column=Column(
            SAEnum(ReservationStatus, name="reservation_status", native_enum=False),
            nullable=False,
        )
    )
    to_status: ReservationStatus = Field(
        sa_column=Column(
            SAEnum(ReservationStatus, name="reservation_status", native_enum=False),
            nullable=False,
        )
    )
    changed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )


class ReservationProviderRequestModel(SQLModel, table=True):
    __tablename__ = "reservation_provider_requests"

    id: int | None = Field(default=None, primary_key=True)
    reservation_code: str = Field(
        sa_column=Column(
            String(64),
            ForeignKey("reservations.reservation_code", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    provider_code: str = Field(sa_column=Column(String(40), nullable=False, index=True))
    request_type: str = Field(sa_column=Column(String(20), nullable=False))
    request_payload: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    response_payload: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    status: str = Field(sa_column=Column(String(20), nullable=False))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )
    responded_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))


class RentalAddonModel(SQLModel, table=True):
    __tablename__ = "rental_addons"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(sa_column=Column(String(3), nullable=False, unique=True))
    name: str = Field(sa_column=Column(String(80), nullable=False))
    category: AddonCategory = Field(
        sa_column=Column(
            SAEnum(AddonCategory, name="addon_category", native_enum=False),
            nullable=False,
        )
    )
    description: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    is_active: bool = Field(default=True)
    sort_order: int = Field(default=100)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )


class ReservationAddonModel(SQLModel, table=True):
    __tablename__ = "reservation_addons"

    id: int | None = Field(default=None, primary_key=True)
    reservation_code: str = Field(
        sa_column=Column(
            String(64),
            nullable=False,
            index=True,
        )
    )
    addon_code: str = Field(sa_column=Column(String(3), nullable=False, index=True))
    addon_name_snapshot: str = Field(sa_column=Column(String(80), nullable=False))
    addon_category_snapshot: str = Field(sa_column=Column(String(20), nullable=False))
    quantity: int = Field(default=1)
    unit_price: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    total_price: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    currency_code: str = Field(default="USD", sa_column=Column(String(3), nullable=False))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )


class ProviderOutboxEventModel(SQLModel, table=True):
    __tablename__ = "provider_outbox_events"

    id: int | None = Field(default=None, primary_key=True)
    aggregate_id: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    event_type: str = Field(sa_column=Column(String(80), nullable=False))
    payload: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    status: str = Field(default="PENDING", sa_column=Column(String(20), nullable=False, index=True))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            index=True,
        ),
    )
