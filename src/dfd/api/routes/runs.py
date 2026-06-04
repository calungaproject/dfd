"""Pipeline runs endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from dfd.common import db

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("")
def list_runs(
    pipeline_type: str | None = None,
    status: str | None = None,
    package_name: str | None = None,
    days: int | None = None,
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    root_cause: str | None = None,
    root_cause_search: str | None = None,
    has_root_cause: bool | None = None,
    taxonomy_matched: bool | None = None,
    name_search: str | None = None,
    page: int = 1,
    per_page: int = 200,
):
    """List pipeline runs with optional filters and pagination."""
    runs, total, counts = db.get_pipeline_runs(
        pipeline_type_id=pipeline_type,
        status=status,
        package_name=package_name,
        days=days,
        from_date=from_date,
        to_date=to_date,
        root_cause=root_cause,
        root_cause_search=root_cause_search,
        has_root_cause=has_root_cause,
        taxonomy_matched=taxonomy_matched,
        name_search=name_search,
        page=page,
        per_page=per_page,
    )
    return {
        "runs": runs,
        "total": total,
        "page": page,
        "per_page": per_page,
        "counts": counts,
    }


@router.get("/{pipeline_run_id}")
def get_run(pipeline_run_id: str):
    """Get a single pipeline run with its latest analysis."""
    run = db.get_pipeline_run_detail(pipeline_run_id)
    if not run:
        raise HTTPException(
            status_code=404, detail="Pipeline run not found"
        )
    run["board_entries"] = db.get_board_entries(pipeline_run_id)
    return run


@router.get("/{pipeline_run_id}/history")
def get_run_history(pipeline_run_id: str):
    """Get all analysis versions for a pipeline run."""
    history = db.get_analysis_history(pipeline_run_id)
    return {"pipeline_run_id": pipeline_run_id, "versions": history}
