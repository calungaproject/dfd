"""Cost tracking endpoint — LLM usage and spend data."""

from __future__ import annotations

from fastapi import APIRouter

from dfd.common import db

router = APIRouter(prefix="/api/costs", tags=["costs"])


@router.get("")
def get_costs(days: int = 30):
    """Cost summary: by type, daily breakdown, and recent entries."""
    return db.get_cost_summary(days=days)
