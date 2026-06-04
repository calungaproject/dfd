"""Statistics endpoint — aggregated data for dashboard charts."""

from __future__ import annotations

from fastapi import APIRouter

from dfd.common import db

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
def get_stats(
    pipeline_type: str | None = None,
    days: int = 30,
):
    """Aggregated stats: totals, pass rate, daily breakdown, root causes."""
    return db.get_stats(pipeline_type_id=pipeline_type, days=days)
