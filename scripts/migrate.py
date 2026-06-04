#!/usr/bin/env python3
"""Run SQL migrations against the DFD database.

Tracks applied migrations in a `schema_migrations` table.
Migrations are applied in filename order (001_, 002_, etc.).

Usage:
    python scripts/migrate.py                    # uses DATABASE_URL env var
    python scripts/migrate.py --database-url postgres://...
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DFD database migrations")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL connection string (default: $DATABASE_URL)",
    )
    args = parser.parse_args()

    if not args.database_url:
        print("ERROR: DATABASE_URL not set. Pass --database-url or export DATABASE_URL.", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(args.database_url)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(1)")

        _ensure_migrations_table(conn)
        applied = _get_applied_migrations(conn)
        pending = _get_pending_migrations(applied)

        if not pending:
            print("All migrations already applied.")
            return

        for migration_file in pending:
            _apply_migration(conn, migration_file)

        print(f"Applied {len(pending)} migration(s) successfully.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_migrations_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )"""
        )
    conn.commit()


def _get_applied_migrations(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT filename FROM schema_migrations")
        return {row[0] for row in cur.fetchall()}


def _get_pending_migrations(applied: set[str]) -> list[Path]:
    all_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    return [f for f in all_files if f.name not in applied]


def _apply_migration(conn, migration_file: Path) -> None:
    print(f"Applying {migration_file.name}...")
    sql = migration_file.read_text()

    with conn.cursor() as cur:
        cur.execute(sql)
        cur.execute(
            "INSERT INTO schema_migrations (filename) VALUES (%s)",
            (migration_file.name,),
        )
    conn.commit()
    print(f"  Applied {migration_file.name}")


if __name__ == "__main__":
    main()
