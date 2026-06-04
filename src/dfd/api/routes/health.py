"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from dfd.common import db

router = APIRouter()


@router.get("/health")
def health():
    """Verify DB connectivity and return diagnostics."""
    return db.check_db_health()
