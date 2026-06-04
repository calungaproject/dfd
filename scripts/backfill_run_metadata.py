#!/usr/bin/env python3
"""Backfill package_name, source_url, and pipeline_url from stored pipelinerun_json.

Runs are collected with ON CONFLICT DO NOTHING, so fields added after
initial collection remain NULL. This script extracts them from the JSONB
column that was stored at collection time.

Usage:
    source .env
    python scripts/backfill_run_metadata.py
"""

from __future__ import annotations

import json
import os
import sys

import psycopg2


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set.", file=sys.stderr)
        sys.exit(1)

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    from dfd.collector.kubearchive import (
        _extract_package_name,
        _extract_package_version,
        _extract_pipeline_url,
        _extract_source_url,
    )

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, pipelinerun_json, package_name, source_url, pipeline_url
                   FROM pipeline_runs
                   WHERE pipelinerun_json IS NOT NULL
                     AND (package_name IS NULL OR source_url IS NULL OR pipeline_url IS NULL)"""
            )
            rows = cur.fetchall()
            print(f"Found {len(rows)} rows to check")

            updated = 0
            for run_id, pj, existing_pkg, existing_src, existing_pipe in rows:
                data = pj if isinstance(pj, dict) else json.loads(pj)
                labels = data.get("metadata", {}).get("labels", {})
                annotations = data.get("metadata", {}).get("annotations", {})

                pkg = existing_pkg or _extract_package_name(labels, annotations)
                ver = _extract_package_version(labels, annotations) if not existing_pkg else None
                src = existing_src or _extract_source_url(labels, annotations)
                pipe = existing_pipe or _extract_pipeline_url(labels, annotations)

                updates = []
                values = []
                if not existing_pkg and pkg:
                    updates.append("package_name = %s")
                    values.append(pkg)
                    updates.append("package_version = %s")
                    values.append(ver)
                if not existing_src and src:
                    updates.append("source_url = %s")
                    values.append(src)
                if not existing_pipe and pipe:
                    updates.append("pipeline_url = %s")
                    values.append(pipe)

                if updates:
                    values.append(run_id)
                    cur.execute(
                        f"UPDATE pipeline_runs SET {', '.join(updates)} WHERE id = %s",
                        values,
                    )
                    updated += 1

            conn.commit()
            print(f"Updated {updated}/{len(rows)} rows")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
