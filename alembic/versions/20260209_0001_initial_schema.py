"""initial schema

Revision ID: 20260209_0001
Revises:
Create Date: 2026-02-09 19:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260209_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

reservation_status = sa.Enum(
    "CREATED",
    "PAYMENT_IN_PROGRESS",
    "PAID",
    "SUPPLIER_CONFIRMED",
    "CANCELLED",
    name="reservation_status",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_suppliers_code", "suppliers", ["code"], unique=True)

    op.create_table(
        "offices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("supplier_code", sa.String(length=40), nullable=False),
        sa.Column("office_code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("city", sa.String(length=80), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["supplier_code"], ["suppliers.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("office_code"),
    )
    op.create_index("ix_offices_supplier_code", "offices", ["supplier_code"], unique=False)
    op.create_index("ix_offices_office_code", "offices", ["office_code"], unique=True)

    op.create_table(
        "reservations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reservation_code", sa.String(length=64), nullable=False),
        sa.Column("status", reservation_status, nullable=False),
        sa.Column("supplier_code", sa.String(length=40), nullable=False),
        sa.Column("pickup_office_code", sa.String(length=40), nullable=False),
        sa.Column("dropoff_office_code", sa.String(length=40), nullable=False),
        sa.Column("pickup_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dropoff_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("customer_snapshot", sa.JSON(), nullable=True),
        sa.Column("vehicle_snapshot", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reservation_code"),
    )
    op.create_index("ix_reservations_reservation_code", "reservations", ["reservation_code"], unique=True)

    op.create_table(
        "reservation_contacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reservation_code", sa.String(length=64), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=190), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.ForeignKeyConstraint(["reservation_code"], ["reservations.reservation_code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reservation_code"),
    )
    op.create_index(
        "ix_reservation_contacts_reservation_code",
        "reservation_contacts",
        ["reservation_code"],
        unique=True,
    )

    op.create_table(
        "reservation_status_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reservation_code", sa.String(length=64), nullable=False),
        sa.Column("from_status", reservation_status, nullable=False),
        sa.Column("to_status", reservation_status, nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["reservation_code"], ["reservations.reservation_code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reservation_status_history_reservation_code",
        "reservation_status_history",
        ["reservation_code"],
        unique=False,
    )

    op.create_table(
        "reservation_provider_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reservation_code", sa.String(length=64), nullable=False),
        sa.Column("provider_code", sa.String(length=40), nullable=False),
        sa.Column("request_type", sa.String(length=20), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=True),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["reservation_code"], ["reservations.reservation_code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reservation_provider_requests_reservation_code",
        "reservation_provider_requests",
        ["reservation_code"],
        unique=False,
    )
    op.create_index(
        "ix_reservation_provider_requests_provider_code",
        "reservation_provider_requests",
        ["provider_code"],
        unique=False,
    )

    op.create_table(
        "provider_outbox_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("aggregate_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provider_outbox_events_aggregate_id",
        "provider_outbox_events",
        ["aggregate_id"],
        unique=False,
    )
    op.create_index(
        "ix_provider_outbox_events_status",
        "provider_outbox_events",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_provider_outbox_events_created_at",
        "provider_outbox_events",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_provider_outbox_events_created_at", table_name="provider_outbox_events")
    op.drop_index("ix_provider_outbox_events_status", table_name="provider_outbox_events")
    op.drop_index("ix_provider_outbox_events_aggregate_id", table_name="provider_outbox_events")
    op.drop_table("provider_outbox_events")

    op.drop_index(
        "ix_reservation_provider_requests_provider_code",
        table_name="reservation_provider_requests",
    )
    op.drop_index(
        "ix_reservation_provider_requests_reservation_code",
        table_name="reservation_provider_requests",
    )
    op.drop_table("reservation_provider_requests")

    op.drop_index(
        "ix_reservation_status_history_reservation_code",
        table_name="reservation_status_history",
    )
    op.drop_table("reservation_status_history")

    op.drop_index(
        "ix_reservation_contacts_reservation_code",
        table_name="reservation_contacts",
    )
    op.drop_table("reservation_contacts")

    op.drop_index("ix_reservations_reservation_code", table_name="reservations")
    op.drop_table("reservations")

    op.drop_index("ix_offices_office_code", table_name="offices")
    op.drop_index("ix_offices_supplier_code", table_name="offices")
    op.drop_table("offices")

    op.drop_index("ix_suppliers_code", table_name="suppliers")
    op.drop_table("suppliers")
