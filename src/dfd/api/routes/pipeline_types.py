"""Pipeline types endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from dfd.common import db

router = APIRouter(prefix="/api")


@router.get("/pipeline-types")
def list_pipeline_types():
    rows = db.get_pipeline_types()
    return [
        {
            "id": r["id"],
            "display_name": r["display_name"],
            "description": r.get("description", ""),
        }
        for r in rows
        if r.get("enabled", True)
    ]
