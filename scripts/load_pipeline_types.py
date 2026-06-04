#!/usr/bin/env python3
"""Load pipeline type definitions from a YAML config file into the database.

Performs an upsert — inserts new pipeline types and updates existing ones.

Usage:
    python scripts/load_pipeline_types.py                          # uses pipeline_types.yaml
    python scripts/load_pipeline_types.py --config my_types.yaml
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2
import yaml

DEFAULT_CONFIG = Path(__file__).parent.parent / "pipeline_types.yaml"

UPSERT_SQL = """
INSERT INTO pipeline_types (id, display_name, label_selector, namespace, description, enabled)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    label_selector = EXCLUDED.label_selector,
    namespace = EXCLUDED.namespace,
    description = EXCLUDED.description,
    enabled = EXCLUDED.enabled
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Load pipeline types from YAML into DB")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Path to pipeline_types.yaml (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL connection string (default: $DATABASE_URL)",
    )
    args = parser.parse_args()

    if not args.database_url:
        print(
            "ERROR: DATABASE_URL not set. Pass --database-url or export DATABASE_URL.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not args.config.exists():
        print(f"ERROR: Config file not found: {args.config}", file=sys.stderr)
        print(f"  Copy pipeline_types.yaml.example to {args.config} and edit it.", file=sys.stderr)
        sys.exit(1)

    with open(args.config) as f:
        data = yaml.safe_load(f)

    pipeline_types = data.get("pipeline_types", [])
    if not pipeline_types:
        print("ERROR: No pipeline_types found in config file.", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(args.database_url)
    try:
        with conn.cursor() as cur:
            for pt in pipeline_types:
                required = ["id", "display_name", "label_selector", "namespace"]
                missing = [k for k in required if not pt.get(k)]
                if missing:
                    print(f"ERROR: Pipeline type missing fields {missing}: {pt}", file=sys.stderr)
                    sys.exit(1)

                enabled = pt.get("enabled", True)
                cur.execute(UPSERT_SQL, (
                    pt["id"],
                    pt["display_name"],
                    pt["label_selector"],
                    pt["namespace"],
                    pt.get("description", ""),
                    enabled,
                ))
                status = "" if enabled else " [disabled]"
                print(f"  Loaded: {pt['id']} (namespace={pt['namespace']}){status}")

        conn.commit()
        print(f"Loaded {len(pipeline_types)} pipeline type(s) successfully.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
