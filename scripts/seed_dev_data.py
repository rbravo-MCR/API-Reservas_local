from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from reservas_api.infrastructure.db.session import build_database_url
from reservas_api.shared.config.settings import settings


def _sync_database_url() -> str:
    url = make_url(build_database_url(settings))
    drivername = url.drivername.replace("aiomysql", "pymysql")
    return url.set(drivername=drivername).render_as_string(hide_password=False)


def main() -> None:
    sql_path = Path(__file__).with_name("seed_dev_data.sql")
    if not sql_path.exists():
        raise FileNotFoundError(f"Seed SQL file not found: {sql_path}")

    statements = [stmt.strip() for stmt in sql_path.read_text(encoding="utf-8").split(";") if stmt.strip()]
    engine = create_engine(_sync_database_url(), pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
    finally:
        engine.dispose()

    print("Seed data applied successfully.")


if __name__ == "__main__":
    main()
