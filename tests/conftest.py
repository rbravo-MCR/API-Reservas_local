import os
import re
import uuid

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession

# Ensure model metadata is registered before creating/dropping tables.
from reservas_api.infrastructure.db.models import (  # noqa: F401
    OfficeModel,
    ProviderOutboxEventModel,
    ReservationContactModel,
    ReservationModel,
    ReservationProviderRequestModel,
    ReservationStatusHistoryModel,
    SupplierModel,
)

load_dotenv()

TABLES_TRUNCATE_ORDER = [
    "offices",
    "suppliers",
    "reservation_provider_requests",
    "reservation_contacts",
    "reservation_status_history",
    "provider_outbox_events",
    "reservations",
]


def _load_mysql_test_urls() -> tuple[str, str]:
    raw_test_url = os.getenv("MYSQL_TEST_DATABASE_URL")
    raw_default_url = os.getenv("DATABASE_URL")
    raw_url = raw_test_url or raw_default_url
    if not raw_url:
        pytest.fail("Missing MYSQL_TEST_DATABASE_URL (or DATABASE_URL) for MySQL tests.")

    url = make_url(raw_url)
    if url.get_backend_name() != "mysql":
        pytest.fail("Test database must use MySQL.")

    if raw_test_url:
        if not (url.database and url.database.endswith("_test")):
            pytest.fail("MYSQL_TEST_DATABASE_URL database name must end with '_test'.")
        test_url = url
    else:
        if not url.database:
            pytest.fail("DATABASE_URL must include a database name.")
        database = url.database if url.database.endswith("_test") else f"{url.database}_test"
        test_url = url.set(database=database)

    async_url = test_url.render_as_string(hide_password=False)
    sync_drivername = (
        "mysql+pymysql"
        if test_url.drivername == "mysql"
        else test_url.drivername.replace("aiomysql", "pymysql")
    )
    sync_url = (
        URL.create(
            drivername=sync_drivername,
            username=test_url.username,
            password=test_url.password,
            host=test_url.host,
            port=test_url.port,
            database=test_url.database,
            query=test_url.query,
        )
        .render_as_string(hide_password=False)
    )
    return async_url, sync_url


def _ensure_test_database_exists(sync_url: str) -> None:
    parsed_url = make_url(sync_url)
    if not parsed_url.database:
        pytest.fail("Test database URL must include a database name.")

    database = parsed_url.database
    if not re.fullmatch(r"[A-Za-z0-9_]+", database):
        pytest.fail("Test database name contains unsupported characters.")

    admin_url = (
        URL.create(
            drivername=parsed_url.drivername,
            username=parsed_url.username,
            password=parsed_url.password,
            host=parsed_url.host,
            port=parsed_url.port,
            database=None,
            query=parsed_url.query,
        )
        .render_as_string(hide_password=False)
    )
    engine = create_engine(admin_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{database}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
                )
            )
    finally:
        engine.dispose()


def _truncate_tables_sync(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in TABLES_TRUNCATE_ORDER:
            conn.execute(text(f"TRUNCATE TABLE `{table}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


def _drop_database(sync_url: str) -> None:
    parsed_url = make_url(sync_url)
    if not parsed_url.database:
        return
    database = parsed_url.database
    if not re.fullmatch(r"[A-Za-z0-9_]+", database):
        return

    admin_url = (
        URL.create(
            drivername=parsed_url.drivername,
            username=parsed_url.username,
            password=parsed_url.password,
            host=parsed_url.host,
            port=parsed_url.port,
            database=None,
            query=parsed_url.query,
        )
        .render_as_string(hide_password=False)
    )
    engine = create_engine(admin_url, pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS `{database}`"))
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def mysql_test_urls() -> tuple[str, str]:
    base_async_url, base_sync_url = _load_mysql_test_urls()
    base_async = make_url(base_async_url)
    base_sync = make_url(base_sync_url)

    suffix = uuid.uuid4().hex[:8]
    isolated_db = f"{base_sync.database}_{suffix}"
    if len(isolated_db) > 64:
        isolated_db = isolated_db[:64]

    async_url = base_async.set(database=isolated_db).render_as_string(hide_password=False)
    sync_url = base_sync.set(database=isolated_db).render_as_string(hide_password=False)

    _ensure_test_database_exists(sync_url)
    bootstrap_engine = create_engine(sync_url, pool_pre_ping=True)
    try:
        SQLModel.metadata.create_all(bootstrap_engine, checkfirst=False)
    finally:
        bootstrap_engine.dispose()

    try:
        yield async_url, sync_url
    finally:
        _drop_database(sync_url)


@pytest.fixture(scope="session")
def mysql_sync_engine(mysql_test_urls: tuple[str, str]):
    _, sync_url = mysql_test_urls
    engine = create_engine(sync_url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="function")
def reset_mysql_schema(mysql_sync_engine):
    _truncate_tables_sync(mysql_sync_engine)
    return mysql_sync_engine


@pytest_asyncio.fixture(scope="function")
async def mysql_async_session_factory(
    mysql_test_urls: tuple[str, str],
) -> async_sessionmaker[AsyncSession]:
    async_url, _ = mysql_test_urls
    engine = create_async_engine(async_url, poolclass=NullPool, pool_pre_ping=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            for table in TABLES_TRUNCATE_ORDER:
                await conn.execute(text(f"TRUNCATE TABLE `{table}`"))
            await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    finally:
        await engine.dispose()
