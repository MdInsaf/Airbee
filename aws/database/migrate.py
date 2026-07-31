#!/usr/bin/env python3
"""Apply AIR BEE SQL migrations in checksum-verified order."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path

import psycopg2


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def _connection_kwargs(args: argparse.Namespace) -> dict:
    return {
        "host": args.host or os.environ.get("DB_HOST", "localhost"),
        "port": args.port or int(os.environ.get("DB_PORT", "5432")),
        "dbname": args.name or os.environ.get("DB_NAME", "airbee"),
        "user": args.user or os.environ.get("DB_USER", "airbee"),
        "password": args.password or os.environ.get("DB_PASSWORD", ""),
        "sslmode": args.sslmode or os.environ.get("DB_SSLMODE", "prefer"),
        "connect_timeout": 15,
    }


def apply_migrations(connection) -> list[str]:
    paths = sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    if not paths:
        raise RuntimeError(f"No migrations found in {MIGRATIONS_DIR}")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS airbee_schema_migrations (
              version TEXT PRIMARY KEY,
              checksum TEXT NOT NULL,
              applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    connection.commit()

    applied = []
    for path in paths:
        sql = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT checksum FROM airbee_schema_migrations WHERE version = %s",
                [path.name],
            )
            row = cursor.fetchone()

        if row:
            if row[0] != checksum:
                raise RuntimeError(
                    f"Migration checksum changed after application: {path.name}"
                )
            continue

        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                cursor.execute(
                    """
                    INSERT INTO airbee_schema_migrations (version, checksum)
                    VALUES (%s, %s)
                    """,
                    [path.name, checksum],
                )
            connection.commit()
            applied.append(path.name)
        except Exception:
            connection.rollback()
            raise

    return applied


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--name")
    parser.add_argument("--user")
    parser.add_argument("--password")
    parser.add_argument("--sslmode")
    args = parser.parse_args()

    with psycopg2.connect(**_connection_kwargs(args)) as connection:
        applied = apply_migrations(connection)

    if applied:
        print("Applied migrations:")
        for version in applied:
            print(f"  {version}")
    else:
        print("Database is already up to date.")


if __name__ == "__main__":
    main()
