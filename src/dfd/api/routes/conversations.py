"""Conversation log endpoints — full agent reasoning from S3."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from dfd.common import db, s3
from dfd.common.config import Settings

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("/{pipeline_run_id}")
def get_conversation(pipeline_run_id: str):
    """Get the full conversation log for a pipeline run from S3."""
    log = db.get_conversation_log(pipeline_run_id)
    if not log:
        raise HTTPException(
            status_code=404,
            detail="No conversation log found",
        )

    settings = Settings()
    full_log = s3.read_json(settings.s3_bucket, log["s3_key"])
    if full_log is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation log not found in S3",
        )

    return {
        "pipeline_run_id": pipeline_run_id,
        "analysis_version": log["analysis_version"],
        "summary": log.get("summary"),
        "agent_sequence": log.get("agent_sequence"),
        "conversation": full_log,
    }
