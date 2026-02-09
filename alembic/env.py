from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from reservas_api.infrastructure.db.models import (  # noqa: E402,F401
    OfficeModel,
    ProviderOutboxEventModel,
    ReservationContactModel,
    ReservationModel,
    ReservationProviderRequestModel,
    ReservationStatusHistoryModel,
    SupplierModel,
)
from reservas_api.infrastructure.db.session import build_database_url  # noqa: E402
from reservas_api.shared.config.settings import settings  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def _resolve_database_url() -> str:
    env_database_url = os.getenv("DATABASE_URL")
    if env_database_url:
        return env_database_url
    return build_database_url(settings)


def _to_sync_driver_url(url: str) -> str:
    if "+aiomysql" in url:
        return url.replace("+aiomysql", "+pymysql")
    return url


def run_migrations_offline() -> None:
    url = _to_sync_driver_url(_resolve_database_url())
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _to_sync_driver_url(_resolve_database_url())
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
