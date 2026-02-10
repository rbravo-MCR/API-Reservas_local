from __future__ import annotations

import argparse
import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def _build_database_url() -> str:
    raw_database_url = os.getenv("DATABASE_URL", "").strip()
    if raw_database_url:
        return raw_database_url.replace("mysql+aiomysql://", "mysql+pymysql://")

    mysql_host = os.getenv("MYSQL_HOST", "localhost")
    mysql_port = os.getenv("MYSQL_PORT", "3306")
    mysql_user = os.getenv("MYSQL_USER", "root")
    mysql_password = quote_plus(os.getenv("MYSQL_PASSWORD", ""))
    mysql_database = os.getenv("MYSQL_DATABASE", "reservas")
    return (
        "mysql+pymysql://"
        f"{mysql_user}:{mysql_password}@{mysql_host}:{mysql_port}/{mysql_database}"
    )


def _scalar(engine: Engine, query: str, params: dict[str, object] | None = None) -> int:
    with engine.begin() as connection:
        result = connection.execute(text(query), params or {})
        value = result.scalar_one()
        return int(value)


def _build_report(
    *,
    run_id: str,
    created_for_run: int,
    outbox_for_run: int,
    missing_or_extra_outbox: int,
    duplicate_codes_global: int,
    duplicate_codes_for_run: int,
) -> str:
    expected_outbox = created_for_run * 2
    status = "PASS"
    issues: list[str] = []

    if duplicate_codes_global > 0:
        status = "FAIL"
        issues.append("Duplicate reservation_code detected globally.")
    if duplicate_codes_for_run > 0:
        status = "FAIL"
        issues.append("Duplicate reservation_code detected in stress run scope.")
    if missing_or_extra_outbox > 0:
        status = "FAIL"
        issues.append("At least one reservation in run scope does not have exactly 2 outbox events.")

    lines: list[str] = []
    lines.append("# Stress Integrity Report")
    lines.append("")
    lines.append(f"- Run id: `{run_id}`")
    lines.append(f"- Overall status: **{status}**")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    lines.append(f"| Reservations created in run scope | {created_for_run} |")
    lines.append(f"| Outbox rows in run scope | {outbox_for_run} |")
    lines.append(f"| Expected outbox rows (2 per reservation) | {expected_outbox} |")
    lines.append(f"| Reservations with outbox count != 2 | {missing_or_extra_outbox} |")
    lines.append(f"| Duplicate reservation codes (global) | {duplicate_codes_global} |")
    lines.append(f"| Duplicate reservation codes (run scope) | {duplicate_codes_for_run} |")
    lines.append("")
    if issues:
        lines.append("## Findings")
        lines.extend(f"- {issue}" for issue in issues)
    else:
        lines.append("No integrity issues detected for stress run scope.")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate reservation integrity after stress tests.")
    parser.add_argument("--run-id", required=True, help="Stress run id used in test payload emails.")
    parser.add_argument(
        "--output",
        default="artifacts/stress/integrity.md",
        help="Markdown output path.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 when integrity checks fail.",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()
    output_path = Path(args.output)

    engine = create_engine(_build_database_url(), pool_pre_ping=True)
    try:
        run_like = f"stress.{args.run_id}.%"
        created_for_run = _scalar(
            engine,
            """
            SELECT COUNT(*)
            FROM reservations r
            WHERE JSON_UNQUOTE(JSON_EXTRACT(r.customer_snapshot, '$.email')) LIKE :run_like
            """,
            {"run_like": run_like},
        )
        outbox_for_run = _scalar(
            engine,
            """
            SELECT COUNT(*)
            FROM provider_outbox_events oe
            JOIN reservations r ON r.reservation_code = oe.aggregate_id
            WHERE JSON_UNQUOTE(JSON_EXTRACT(r.customer_snapshot, '$.email')) LIKE :run_like
            """,
            {"run_like": run_like},
        )
        missing_or_extra_outbox = _scalar(
            engine,
            """
            SELECT COUNT(*)
            FROM (
                SELECT r.reservation_code, COUNT(oe.id) AS outbox_count
                FROM reservations r
                LEFT JOIN provider_outbox_events oe
                    ON oe.aggregate_id = r.reservation_code
                WHERE JSON_UNQUOTE(JSON_EXTRACT(r.customer_snapshot, '$.email')) LIKE :run_like
                GROUP BY r.reservation_code
                HAVING COUNT(oe.id) <> 2
            ) x
            """,
            {"run_like": run_like},
        )
        duplicate_codes_global = _scalar(
            engine,
            """
            SELECT COUNT(*)
            FROM (
                SELECT reservation_code
                FROM reservations
                GROUP BY reservation_code
                HAVING COUNT(*) > 1
            ) dup
            """,
        )
        duplicate_codes_for_run = _scalar(
            engine,
            """
            SELECT COUNT(*)
            FROM (
                SELECT r.reservation_code
                FROM reservations r
                WHERE JSON_UNQUOTE(JSON_EXTRACT(r.customer_snapshot, '$.email')) LIKE :run_like
                GROUP BY r.reservation_code
                HAVING COUNT(*) > 1
            ) dup_run
            """,
            {"run_like": run_like},
        )
    finally:
        engine.dispose()

    report = _build_report(
        run_id=args.run_id,
        created_for_run=created_for_run,
        outbox_for_run=outbox_for_run,
        missing_or_extra_outbox=missing_or_extra_outbox,
        duplicate_codes_global=duplicate_codes_global,
        duplicate_codes_for_run=duplicate_codes_for_run,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    if args.strict:
        failed = (
            duplicate_codes_global > 0
            or duplicate_codes_for_run > 0
            or missing_or_extra_outbox > 0
        )
        return 1 if failed else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
