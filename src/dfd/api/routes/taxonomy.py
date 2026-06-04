"""Taxonomy management endpoints — rules and proposals."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dfd.common import db

router = APIRouter(prefix="/api/taxonomy", tags=["taxonomy"])


class RuleUpdate(BaseModel):
    root_cause: str | None = None
    category: str | None = None
    error_signature: str | None = None
    priority_rule: str | None = None
    investigation_recipe: str | None = None


class MergeRequest(BaseModel):
    target_rule_id: int


@router.get("/{pipeline_type_id}")
def get_rules(pipeline_type_id: str):
    """Get taxonomy rules for a pipeline type."""
    return db.get_taxonomy_rules(pipeline_type_id)


@router.get("/{pipeline_type_id}/proposals")
def get_proposals(pipeline_type_id: str):
    """Get pending rule proposals for a pipeline type."""
    return db.get_pending_proposals(pipeline_type_id)


@router.post("/{pipeline_type_id}/proposals/{proposal_id}/accept")
def accept_proposal(pipeline_type_id: str, proposal_id: int):
    """Accept a pending rule proposal."""
    proposals = db.get_pending_proposals(pipeline_type_id)
    proposal = next(
        (p for p in proposals if p["id"] == proposal_id), None
    )
    if not proposal:
        raise HTTPException(
            status_code=404, detail="Proposal not found or not pending"
        )

    existing = db.get_taxonomy_rules(pipeline_type_id)
    next_priority = (
        max((r["priority_order"] for r in existing), default=0) + 1
    )

    rule_id = db.insert_taxonomy_rule(
        pipeline_type_id=pipeline_type_id,
        root_cause=proposal["root_cause"],
        category=proposal["category"],
        error_signature=proposal["error_signature"],
        priority_order=next_priority,
        priority_rule=proposal.get("priority_rule"),
        investigation_recipe=proposal.get("investigation_recipe"),
        origin="agent_proposed_reviewed",
    )

    db.update_proposal_status(proposal_id, "accepted")

    unknowns = db.get_recent_unknowns(
        pipeline_type_id, days=90, limit=100
    )
    for u in unknowns:
        db.queue_reanalysis(
            pipeline_run_id=u["pipeline_run_id"],
            pipeline_type_id=pipeline_type_id,
            reason=f"rule_accepted:{proposal['root_cause']}",
            triggered_by="manual",
        )

    return {
        "status": "accepted",
        "rule_id": rule_id,
        "reanalysis_queued": len(unknowns),
    }


@router.post("/{pipeline_type_id}/proposals/{proposal_id}/reject")
def reject_proposal(pipeline_type_id: str, proposal_id: int):
    """Reject a pending rule proposal."""
    db.update_proposal_status(proposal_id, "rejected")
    return {"status": "rejected"}


@router.put("/{pipeline_type_id}/rules/{rule_id}")
def update_rule(
    pipeline_type_id: str, rule_id: int, body: RuleUpdate
):
    """Update a taxonomy rule and queue affected analyses."""
    rules = db.get_taxonomy_rules(pipeline_type_id)
    rule = next((r for r in rules if r["id"] == rule_id), None)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    old_root_cause = rule["root_cause"]

    updated = db.update_taxonomy_rule(
        rule_id,
        root_cause=body.root_cause,
        category=body.category,
        error_signature=body.error_signature,
        priority_rule=body.priority_rule,
        investigation_recipe=body.investigation_recipe,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Rule not found")

    affected = db.get_recent_analyses(
        pipeline_type_id, old_root_cause, days=90, limit=50
    )
    for a in affected:
        db.queue_reanalysis(
            pipeline_run_id=a["pipeline_run_id"],
            pipeline_type_id=pipeline_type_id,
            reason=f"rule_updated:{old_root_cause}",
            triggered_by="manual",
        )

    return {"status": "updated", "reanalysis_queued": len(affected)}


@router.post("/{pipeline_type_id}/rules/{rule_id}/merge")
def merge_rule(
    pipeline_type_id: str, rule_id: int, body: MergeRequest
):
    """Merge a rule into another: relabel analyses, delete source."""
    rules = db.get_taxonomy_rules(pipeline_type_id)
    source = next((r for r in rules if r["id"] == rule_id), None)
    target = next(
        (r for r in rules if r["id"] == body.target_rule_id), None
    )

    if not source:
        raise HTTPException(
            status_code=404, detail="Source rule not found"
        )
    if not target:
        raise HTTPException(
            status_code=404, detail="Target rule not found"
        )
    if rule_id == body.target_rule_id:
        raise HTTPException(
            status_code=400, detail="Cannot merge a rule into itself"
        )

    relabeled = db.relabel_analyses(
        source["root_cause"], target["root_cause"], pipeline_type_id
    )
    db.delete_taxonomy_rule(rule_id)

    return {
        "status": "merged",
        "source": source["root_cause"],
        "target": target["root_cause"],
        "analyses_relabeled": relabeled,
    }


@router.delete("/{pipeline_type_id}/rules/{rule_id}")
def delete_rule(pipeline_type_id: str, rule_id: int):
    """Delete a taxonomy rule and queue affected analyses."""
    rules = db.get_taxonomy_rules(pipeline_type_id)
    rule = next((r for r in rules if r["id"] == rule_id), None)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    root_cause = rule["root_cause"]
    deleted = db.delete_taxonomy_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")

    affected = db.get_recent_analyses(
        pipeline_type_id, root_cause, days=90, limit=50
    )
    for a in affected:
        db.queue_reanalysis(
            pipeline_run_id=a["pipeline_run_id"],
            pipeline_type_id=pipeline_type_id,
            reason=f"rule_deleted:{root_cause}",
            triggered_by="manual",
        )

    return {"status": "deleted", "reanalysis_queued": len(affected)}
