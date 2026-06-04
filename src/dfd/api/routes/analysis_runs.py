"""Analysis runs and re-analysis endpoints."""

from __future__ import annotations

import logging

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dfd.common import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["analysis"])


@router.get("/analysis-runs")
def list_analysis_runs(limit: int = 20):
    """List recent analysis runs."""
    return db.get_analysis_runs(limit=limit)


@router.get("/analysis-runs/{run_id}")
def get_analysis_run(run_id: int):
    """Get a single analysis run with cost breakdown."""
    result = db.get_analysis_run_detail(run_id)
    if not result:
        raise HTTPException(
            status_code=404, detail="Analysis run not found"
        )
    return result


@router.get("/reanalysis/queue")
def get_reanalysis_queue():
    """Get pending re-analysis queue items."""
    return db.get_pending_reanalysis()


class ReanalysisRequest(BaseModel):
    pipeline_type: str
    root_cause: str | None = None
    days: int = 30


@router.post("/reanalysis")
def trigger_reanalysis(body: ReanalysisRequest):
    """Manually trigger re-analysis for a pipeline type."""
    if body.root_cause:
        targets = db.get_recent_analyses(
            body.pipeline_type, body.root_cause, limit=100
        )
    else:
        targets = db.get_recent_unknowns(
            body.pipeline_type, days=body.days, limit=100
        )

    queued = 0
    for t in targets:
        db.queue_reanalysis(
            pipeline_run_id=t["pipeline_run_id"],
            pipeline_type_id=body.pipeline_type,
            reason=f"manual:{body.root_cause or 'unknowns'}",
            triggered_by="manual",
        )
        queued += 1

    return {"queued": queued}


@router.post("/reanalysis/process")
def process_reanalysis_queue_now():
    """Process pending re-analysis queue items immediately."""
    from dfd.analyzer.reanalysis import process_reanalysis_queue
    from dfd.common import claude_client, s3
    from dfd.common.config import Settings

    pending = db.get_pending_reanalysis()
    if not pending:
        return {"processed": 0, "message": "Queue is empty"}

    settings = Settings()
    claude_client.init_client(settings)
    s3.init_s3(settings.s3_endpoint_url or None)

    run_id = db.create_analysis_run(
        trigger="manual",
        hours_back=0,
        pipeline_types=[],
    )

    try:
        processed = asyncio.run(process_reanalysis_queue(settings, run_id))
        total_cost = db.get_analysis_run_total_cost(run_id)
        db.update_analysis_run(
            run_id, status="completed", analyzed_count=processed, total_cost_usd=total_cost,
        )
        return {"processed": processed, "analysis_run_id": run_id}
    except Exception as e:
        logger.error("Re-analysis processing failed: %s", e)
        db.update_analysis_run(run_id, status="failed", error_message=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reanalysis/{pipeline_run_id}")
def trigger_single_reanalysis(pipeline_run_id: str):
    """Queue a single pipeline run for re-analysis."""
    run = db.get_pipeline_run_detail(pipeline_run_id)
    if not run:
        raise HTTPException(
            status_code=404, detail="Pipeline run not found"
        )

    db.queue_reanalysis(
        pipeline_run_id=pipeline_run_id,
        pipeline_type_id=run["pipeline_type_id"],
        reason="manual:single_run",
        triggered_by="manual",
    )
    return {"queued": 1, "pipeline_run_id": pipeline_run_id}
