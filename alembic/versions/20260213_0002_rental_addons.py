"""add rental_addons and reservation_addons tables

Revision ID: 20260213_0002
Revises: 20260209_0001
Create Date: 2026-02-13 10:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260213_0002"
down_revision: str = "20260209_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

addon_category = sa.Enum(
    "coverage",
    "driver",
    "equipment",
    "logistics",
    "convenience",
    name="addon_category",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "rental_addons",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("code", sa.String(length=3), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("category", addon_category, nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    # Seed base addons
    op.execute(
        """
        INSERT INTO rental_addons (code, name, category, description, sort_order, is_active) VALUES
        ('FUL', 'Full Protection', 'coverage', 'Paquete de cobertura total (deducible 0 o reducido segun condiciones).', 10, 1),
        ('ADC', 'Conductor adicional', 'driver', 'Agrega uno o mas conductores autorizados al contrato.', 20, 1),
        ('YNG', 'Cargo conductor joven', 'driver', 'Cargo aplicable por rango de edad segun politicas de arrendadora.', 30, 1),
        ('BAB', 'Silla para bebe/infantil', 'equipment', 'Silla para bebe/nino (sujeto a disponibilidad).', 40, 1),
        ('GPS', 'GPS / Navegacion', 'equipment', 'Dispositivo de navegacion (si aplica).', 50, 1),
        ('WIF', 'Wi-Fi portatil', 'equipment', 'Hotspot movil para internet en ruta.', 60, 1),
        ('SNW', 'Cadenas para nieve', 'equipment', 'Cadenas para nieve (solo destinos/temporadas aplicables).', 70, 1),
        ('ONE', 'One-way', 'logistics', 'Devolucion en una oficina/ciudad distinta a la de recogida.', 80, 1),
        ('DEL', 'Entrega y recoleccion', 'logistics', 'Entrega y/o devolucion en hotel/domicilio (si aplica).', 90, 1),
        ('AFT', 'Servicio fuera de horario', 'logistics', 'Recogida o devolucion fuera de horario de oficina.', 100, 1),
        ('XBR', 'Permiso cruce de frontera', 'logistics', 'Permiso y condiciones para cruzar frontera (si aplica).', 110, 1),
        ('FUE', 'Opcion combustible', 'convenience', 'Prepago o modalidad de tanque segun politica del proveedor.', 120, 1),
        ('CLN', 'Limpieza', 'convenience', 'Cargo por limpieza especial (arena, suciedad excesiva, etc.).', 130, 1),
        ('FLC', 'Cancelacion flexible', 'convenience', 'Permite cancelar sin penalizacion dentro de la ventana definida.', 140, 1)
        """
    )

    op.create_table(
        "reservation_addons",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("reservation_code", sa.String(length=64), nullable=False),
        sa.Column("addon_code", sa.String(length=3), nullable=False),
        sa.Column("addon_name_snapshot", sa.String(length=80), nullable=False),
        sa.Column("addon_category_snapshot", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False, server_default=sa.text("'USD'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reservation_addons_reservation_code", "reservation_addons", ["reservation_code"])
    op.create_index("ix_reservation_addons_addon_code", "reservation_addons", ["addon_code"])


def downgrade() -> None:
    op.drop_index("ix_reservation_addons_addon_code", table_name="reservation_addons")
    op.drop_index("ix_reservation_addons_reservation_code", table_name="reservation_addons")
    op.drop_table("reservation_addons")
    op.drop_table("rental_addons")
