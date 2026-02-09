from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from reservas_api.shared.config.settings import Settings, settings


def build_database_url(app_settings: Settings) -> str:
    """Build async SQLAlchemy URL from explicit URL or MySQL settings."""
    if app_settings.database_url:
        return app_settings.database_url

    password = quote_plus(app_settings.mysql_password)
    return (
        "mysql+aiomysql://"
        f"{app_settings.mysql_user}:{password}@"
        f"{app_settings.mysql_host}:{app_settings.mysql_port}/"
        f"{app_settings.mysql_database}"
    )


def create_session_factory(
    app_settings: Settings = settings,
) -> async_sessionmaker[AsyncSession]:
    """Create async SQLModel session factory configured for MySQL."""
    engine = create_async_engine(
        build_database_url(app_settings),
        echo=app_settings.app_debug,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
