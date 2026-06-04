"""Collection trigger endpoint — API to Collector communication."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from dfd.common import db

router = APIRouter(prefix="/api", tags=["collect"])


class CollectRequest(BaseModel):
    pipeline_types: list[str] | None = None
    hours_back: int | None = None


@router.post("/collect")
def trigger_collection(body: CollectRequest | None = None):
    """Queue a collection run for the collector to pick up."""
    req_id = db.create_collect_request(
        pipeline_types=body.pipeline_types if body else None,
        hours_back=body.hours_back if body else None,
    )
    return {"status": "queued", "request_id": req_id}
