"""Taxonomy management — rendering, validation, and proposal processing.

Uses batch-level consolidation to prevent duplicate taxonomy labels.
Adapted from DFD 2.0 with pipeline_type_id replacing component_id
and categories build/infra/unknown.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from dfd.common import claude_client, db
from dfd.common.models import InvocationType, RuleProposal

logger = logging.getLogger(__name__)

ROOT_CAUSE_RE = re.compile(r"^[a-z][a-z0-9_]{2,50}$")

VALID_CATEGORIES = {"build", "infra", "unknown"}

_CONSOLIDATE_TOOL = {
    "name": "consolidate_proposals",
    "description": (
        "Group semantically equivalent rule proposals into clusters, "
        "pick one canonical label per cluster, and check against existing rules."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "clusters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "canonical_root_cause": {
                            "type": "string",
                            "description": "Best snake_case root_cause label",
                        },
                        "canonical_category": {
                            "type": "string",
                            "enum": ["build", "infra", "unknown"],
                        },
                        "canonical_error_signature": {
                            "type": "string",
                            "description": "Best error_signature (>= 10 chars)",
                        },
                        "canonical_priority_rule": {
                            "type": "string",
                        },
                        "canonical_investigation_recipe": {
                            "type": "string",
                            "description": (
                                "Merged investigation recipe: deterministic numbered steps "
                                "with concrete regex patterns."
                            ),
                        },
                        "proposal_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                        "is_duplicate_of": {
                            "type": "string",
                            "description": "Existing root_cause name if duplicate, or omit.",
                        },
                    },
                    "required": [
                        "canonical_root_cause",
                        "canonical_category",
                        "canonical_error_signature",
                        "canonical_priority_rule",
                        "canonical_investigation_recipe",
                        "proposal_ids",
                    ],
                },
            },
        },
        "required": ["clusters"],
    },
}


def render_taxonomy_markdown(pipeline_type_id: str) -> str:
    """Render taxonomy rules as markdown for agent system prompts."""
    rules = db.get_taxonomy_rules(pipeline_type_id)

    if not rules:
        return (
            f"## Taxonomy for {pipeline_type_id}\n\n"
            "**No taxonomy rules exist yet.**\n\n"
            "This is expected for the first analysis runs. You should:\n"
            "1. Analyze the failure based on the evidence\n"
            "2. Classify as your best assessment of the root cause\n"
            "3. Propose a new taxonomy rule if you identify a clear, recurring pattern\n\n"
            "The taxonomy will build itself organically through the rule proposal process.\n"
        )

    lines = [
        f"## Taxonomy for {pipeline_type_id}",
        "",
        "| # | Root Cause | Category | Error Signature |",
        "|---|-----------|----------|-----------------|",
    ]

    for rule in rules:
        lines.append(
            f"| {rule['priority_order']} | `{rule['root_cause']}` "
            f"| {rule['category']} | {rule['error_signature']} |"
        )

    priority_rules = [r for r in rules if r.get("priority_rule")]
    if priority_rules:
        lines.append("")
        lines.append("### Priority Rules")
        lines.append("")
        for rule in priority_rules:
            lines.append(f"- {rule['priority_rule']}")

    recipes = [r for r in rules if r.get("investigation_recipe")]
    if recipes:
        lines.append("")
        lines.append("### Investigation Recipes")
        lines.append("")
        for rule in recipes:
            lines.append(f"#### `{rule['root_cause']}`")
            lines.append("")
            lines.append(rule["investigation_recipe"])
            lines.append("")

    lines.append("")
    return "\n".join(lines)


def validate_proposal(proposal: RuleProposal) -> list[str]:
    errors: list[str] = []
    if not ROOT_CAUSE_RE.match(proposal.root_cause):
        errors.append(
            f"Invalid root_cause '{proposal.root_cause}': "
            "must be lowercase snake_case, 3-51 chars"
        )
    if proposal.category not in VALID_CATEGORIES:
        errors.append(f"Invalid category '{proposal.category}': must be one of {VALID_CATEGORIES}")
    if len(proposal.error_signature) < 10:
        errors.append(f"Error signature too short ({len(proposal.error_signature)} chars)")
    return errors


def process_proposals(
    pipeline_type_id: str,
    analysis_run_id: int,
    model: str,
) -> int:
    """Process pending rule proposals using batch consolidation.

    Returns the count of newly accepted rules.
    """
    pending = db.get_pending_proposals(pipeline_type_id)
    if not pending:
        return 0

    logger.info("[%s] Processing %d pending rule proposals", pipeline_type_id, len(pending))

    valid_proposals: list[dict[str, Any]] = []
    for p in pending:
        proposal = RuleProposal(
            pipeline_type_id=p["pipeline_type_id"],
            pipeline_run_id=p.get("pipeline_run_id"),
            root_cause=p["root_cause"],
            category=p["category"],
            error_signature=p["error_signature"],
            priority_rule=p["priority_rule"],
            investigation_recipe=p.get("investigation_recipe"),
            reasoning=p.get("reasoning"),
        )
        errors = validate_proposal(proposal)
        if errors:
            logger.warning(
                "[%s] Rejecting proposal %d: %s", pipeline_type_id, p["id"], "; ".join(errors)
            )
            db.update_proposal_status(p["id"], "rejected")
        else:
            valid_proposals.append(p)

    if not valid_proposals:
        return 0

    existing_rules = db.get_taxonomy_rules(pipeline_type_id)

    if len(valid_proposals) == 1 and not existing_rules:
        return _accept_single_proposal(valid_proposals[0], pipeline_type_id, priority_order=1)

    clusters = _consolidate_proposals(valid_proposals, existing_rules, model, analysis_run_id)
    if not clusters:
        logger.warning(
            "[%s] Consolidation returned no clusters — accepting all as-is",
            pipeline_type_id,
        )
        return _accept_all_individually(valid_proposals, existing_rules, pipeline_type_id)

    existing_root_causes = {r["root_cause"] for r in existing_rules}
    next_priority = max((r["priority_order"] for r in existing_rules), default=0) + 1
    accepted_count = 0
    proposal_by_id = {p["id"]: p for p in valid_proposals}

    for cluster in clusters:
        dup_of = cluster.get("is_duplicate_of")
        proposal_ids = cluster.get("proposal_ids", [])

        if dup_of:
            for pid in proposal_ids:
                if pid in proposal_by_id:
                    db.update_proposal_status(pid, "duplicate")
            canonical = cluster["canonical_root_cause"]
            if canonical != dup_of:
                count = db.relabel_analyses(canonical, dup_of, pipeline_type_id)
                if count:
                    logger.info(
                        "[%s] Relabeled %d analyses: %s -> %s",
                        pipeline_type_id, count, canonical, dup_of,
                    )
            continue

        canonical_root_cause = cluster["canonical_root_cause"]

        if canonical_root_cause in existing_root_causes:
            for pid in proposal_ids:
                if pid in proposal_by_id:
                    db.update_proposal_status(pid, "duplicate")
            continue

        rule_id = db.insert_taxonomy_rule(
            pipeline_type_id=pipeline_type_id,
            root_cause=canonical_root_cause,
            category=cluster.get("canonical_category", "unknown"),
            error_signature=cluster.get("canonical_error_signature", ""),
            priority_order=next_priority,
            priority_rule=cluster.get("canonical_priority_rule"),
            investigation_recipe=cluster.get("canonical_investigation_recipe"),
            origin="agent_proposed",
        )

        if rule_id > 0:
            existing_root_causes.add(canonical_root_cause)
            next_priority += 1
            accepted_count += 1

            first = True
            for pid in proposal_ids:
                if pid in proposal_by_id:
                    db.update_proposal_status(pid, "accepted" if first else "duplicate")
                    first = False
                    p = proposal_by_id[pid]
                    if p["root_cause"] != canonical_root_cause:
                        count = db.relabel_analyses(
                            p["root_cause"], canonical_root_cause, pipeline_type_id
                        )
                        if count:
                            logger.info(
                                "[%s] Relabeled %d analyses: %s -> %s",
                                pipeline_type_id, count, p["root_cause"], canonical_root_cause,
                            )

            _queue_unmatched_for_reanalysis(pipeline_type_id, canonical_root_cause)
        else:
            for pid in proposal_ids:
                if pid in proposal_by_id:
                    db.update_proposal_status(pid, "duplicate")

    if accepted_count > 0:
        _queue_unknowns_for_reanalysis(pipeline_type_id)

    logger.info(
        "[%s] Proposal processing complete: %d accepted out of %d",
        pipeline_type_id, accepted_count, len(pending),
    )
    return accepted_count


def _consolidate_proposals(
    pending: list[dict[str, Any]],
    existing_rules: list[dict[str, Any]],
    model: str,
    analysis_run_id: int,
) -> list[dict[str, Any]]:
    proposals_text = "\n".join(
        f"- ID={p['id']}: root_cause=`{p['root_cause']}`, category={p['category']}, "
        f"error_signature=\"{p['error_signature']}\", priority_rule=\"{p['priority_rule']}\", "
        f"investigation_recipe=\"{p.get('investigation_recipe', 'N/A')}\""
        for p in pending
    )

    existing_text = (
        "None — this is a new taxonomy."
        if not existing_rules
        else "\n".join(
            f"- `{r['root_cause']}` ({r['category']}): {r['error_signature']}"
            for r in existing_rules
        )
    )

    system = [
        {
            "type": "text",
            "text": (
                "You are a taxonomy consolidation agent. Group semantically equivalent "
                "rule proposals into clusters, picking one canonical label per cluster.\n\n"
                "## Instructions\n\n"
                "1. Read all pending proposals and existing rules.\n"
                "2. Group proposals that describe the SAME failure pattern into clusters.\n"
                "3. Pick the BEST canonical label (snake_case, 3-51 chars).\n"
                "4. Check each cluster against existing rules (set is_duplicate_of if match).\n"
                "5. For each cluster, create a merged investigation_recipe with concrete "
                "regex patterns.\n\n"
                "Use the consolidate_proposals tool to submit your grouping."
            ),
        }
    ]

    user_message = (
        f"## Pending Proposals\n\n{proposals_text}\n\n"
        f"## Existing Taxonomy Rules\n\n{existing_text}\n\n"
        "Group these proposals into clusters and submit via the consolidate_proposals tool."
    )

    try:
        response = claude_client.send_message(
            system=system,
            messages=[{"role": "user", "content": user_message}],
            model=model,
            max_tokens=8000,
            tools=[_CONSOLIDATE_TOOL],
            thinking_budget=5000,
        )

        cost_entry = claude_client.make_cost_entry(
            response,
            model=model,
            invocation_type=InvocationType.CONSOLIDATION,
            analysis_run_id=analysis_run_id,
        )
        db.insert_cost_entry(cost_entry)

        for tool_call in response.tool_use:
            if tool_call.name == "consolidate_proposals":
                clusters = tool_call.input.get("clusters", [])
                logger.info(
                    "Consolidation produced %d clusters from %d proposals",
                    len(clusters), len(pending),
                )
                return clusters

        logger.warning("Consolidation did not call tool — response: %s", response.text[:200])
        return []

    except Exception as e:
        logger.error("Consolidation failed: %s — falling back to individual acceptance", e)
        return []


def _accept_single_proposal(
    proposal: dict[str, Any], pipeline_type_id: str, priority_order: int
) -> int:
    rule_id = db.insert_taxonomy_rule(
        pipeline_type_id=pipeline_type_id,
        root_cause=proposal["root_cause"],
        category=proposal["category"],
        error_signature=proposal["error_signature"],
        priority_order=priority_order,
        priority_rule=proposal.get("priority_rule"),
        investigation_recipe=proposal.get("investigation_recipe"),
        origin="agent_proposed",
    )
    if rule_id > 0:
        db.update_proposal_status(proposal["id"], "accepted")
        logger.info("[%s] Accepted single proposal: %s", pipeline_type_id, proposal["root_cause"])
        _queue_unknowns_for_reanalysis(pipeline_type_id)
        return 1
    db.update_proposal_status(proposal["id"], "duplicate")
    return 0


def _accept_all_individually(
    proposals: list[dict[str, Any]],
    existing_rules: list[dict[str, Any]],
    pipeline_type_id: str,
) -> int:
    existing_root_causes = {r["root_cause"] for r in existing_rules}
    next_priority = max((r["priority_order"] for r in existing_rules), default=0) + 1
    accepted = 0

    for p in proposals:
        if p["root_cause"] in existing_root_causes:
            db.update_proposal_status(p["id"], "duplicate")
            continue

        rule_id = db.insert_taxonomy_rule(
            pipeline_type_id=pipeline_type_id,
            root_cause=p["root_cause"],
            category=p["category"],
            error_signature=p["error_signature"],
            priority_order=next_priority,
            priority_rule=p.get("priority_rule"),
            investigation_recipe=p.get("investigation_recipe"),
            origin="agent_proposed",
        )
        if rule_id > 0:
            db.update_proposal_status(p["id"], "accepted")
            existing_root_causes.add(p["root_cause"])
            next_priority += 1
            accepted += 1
        else:
            db.update_proposal_status(p["id"], "duplicate")

    if accepted > 0:
        _queue_unknowns_for_reanalysis(pipeline_type_id)
    return accepted


_CONSOLIDATE_NOVEL_TOOL = {
    "name": "consolidate_novel_root_causes",
    "description": (
        "Group semantically equivalent novel root causes into clusters. "
        "For each cluster with 3+ distinct pipeline runs, propose a canonical label."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "clusters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "canonical_root_cause": {"type": "string"},
                        "canonical_category": {
                            "type": "string",
                            "enum": ["build", "infra", "unknown"],
                        },
                        "canonical_error_signature": {"type": "string"},
                        "analysis_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                        "pipeline_run_count": {"type": "integer"},
                        "should_promote": {"type": "boolean"},
                    },
                    "required": [
                        "canonical_root_cause",
                        "canonical_category",
                        "canonical_error_signature",
                        "analysis_ids",
                        "pipeline_run_count",
                        "should_promote",
                    ],
                },
            },
        },
        "required": ["clusters"],
    },
}


def consolidate_novel_root_causes(
    pipeline_type_id: str,
    analysis_run_id: int,
    model: str,
) -> int:
    """Consolidate novel (non-taxonomy) root causes. Auto-promote at 3+ occurrences/90 days."""
    novel = db.get_novel_analyses(pipeline_type_id, days=90)
    if len(novel) < 3:
        return 0

    logger.info("[%s] Consolidating %d novel analyses", pipeline_type_id, len(novel))

    existing_rules = db.get_taxonomy_rules(pipeline_type_id)
    existing_root_causes = {r["root_cause"] for r in existing_rules}

    analyses_text = "\n\n".join(_format_novel_analysis(a) for a in novel)
    existing_text = (
        "None."
        if not existing_rules
        else "\n".join(f"- `{r['root_cause']}` ({r['category']})" for r in existing_rules)
    )

    system = [
        {
            "type": "text",
            "text": (
                "You are a taxonomy consolidation agent. You are given novel failure "
                "classifications not matched to any existing taxonomy rule.\n\n"
                "## Instructions\n\n"
                "1. Group analyses with the SAME failure mechanism into clusters.\n"
                "2. Pick the best canonical label (snake_case, 3-51 chars).\n"
                "3. Count distinct pipeline_run_ids per cluster.\n"
                "4. Set should_promote=true ONLY if 3+ distinct pipeline runs.\n"
                "5. Do NOT create clusters that match existing rules.\n\n"
                "Use the consolidate_novel_root_causes tool."
            ),
        }
    ]

    user_message = (
        f"## Novel Analyses for {pipeline_type_id}\n\n{analyses_text}\n\n"
        f"## Existing Taxonomy Rules (do not duplicate)\n\n{existing_text}\n\n"
        "Group these and identify recurring patterns."
    )

    try:
        response = claude_client.send_message(
            system=system,
            messages=[{"role": "user", "content": user_message}],
            model=model,
            max_tokens=8000,
            tools=[_CONSOLIDATE_NOVEL_TOOL],
            thinking_budget=5000,
        )

        cost_entry = claude_client.make_cost_entry(
            response,
            model=model,
            invocation_type=InvocationType.CONSOLIDATION,
            analysis_run_id=analysis_run_id,
        )
        db.insert_cost_entry(cost_entry)

        clusters = []
        for tool_call in response.tool_use:
            if tool_call.name == "consolidate_novel_root_causes":
                clusters = tool_call.input.get("clusters", [])
                break

        if not clusters:
            return 0

        next_priority = max((r["priority_order"] for r in existing_rules), default=0) + 1
        promoted_count = 0

        for cluster in clusters:
            if not cluster.get("should_promote"):
                continue

            canonical = cluster["canonical_root_cause"]
            if canonical in existing_root_causes:
                continue
            if not ROOT_CAUSE_RE.match(canonical):
                logger.warning("[%s] Skipping invalid label: %s", pipeline_type_id, canonical)
                continue

            rule_id = db.insert_taxonomy_rule(
                pipeline_type_id=pipeline_type_id,
                root_cause=canonical,
                category=cluster.get("canonical_category", "unknown"),
                error_signature=cluster.get("canonical_error_signature", ""),
                priority_order=next_priority,
                origin="auto_consolidation",
            )

            if rule_id > 0:
                existing_root_causes.add(canonical)
                next_priority += 1
                promoted_count += 1

                analysis_ids = cluster.get("analysis_ids", [])
                db.mark_analyses_taxonomy_matched(analysis_ids)

                for a in novel:
                    if a["id"] in analysis_ids and a["root_cause"] != canonical:
                        db.relabel_analyses(a["root_cause"], canonical, pipeline_type_id)

                _queue_unmatched_for_reanalysis(pipeline_type_id, canonical)

                logger.info(
                    "[%s] Promoted: %s (%d pipeline runs)",
                    pipeline_type_id, canonical, cluster.get("pipeline_run_count", 0),
                )

        if promoted_count > 0:
            _queue_unknowns_for_reanalysis(pipeline_type_id)

        return promoted_count

    except Exception as e:
        logger.error("[%s] Novel consolidation failed: %s", pipeline_type_id, e)
        return 0


def _format_novel_analysis(a: dict) -> str:
    lines = [
        f"### analysis_id={a['id']}  pipeline_run_id={a['pipeline_run_id']}",
        f"- **root_cause:** {a['root_cause']}",
        f"- **category:** {a['category']}",
    ]
    if a.get("failed_task"):
        lines.append(f"- **failed_task:** {a['failed_task']}")
    if a.get("error_message"):
        lines.append(f"- **error_message:** {a['error_message'][:300]}")
    if a.get("evidence"):
        lines.append(f"- **evidence:** {a['evidence'][:500]}")
    if a.get("details"):
        lines.append(f"- **details:** {a['details'][:500]}")
    return "\n".join(lines)


def _queue_unknowns_for_reanalysis(pipeline_type_id: str) -> None:
    unknowns = db.get_recent_unknowns(pipeline_type_id, days=90, limit=100)
    queued = 0
    for analysis in unknowns:
        db.queue_reanalysis(
            pipeline_run_id=analysis["pipeline_run_id"],
            pipeline_type_id=pipeline_type_id,
            reason="new_rules_accepted",
            triggered_by="auto",
        )
        queued += 1
    if queued:
        logger.info("[%s] Queued %d unknowns for re-analysis", pipeline_type_id, queued)


def _queue_unmatched_for_reanalysis(
    pipeline_type_id: str, root_cause: str
) -> None:
    """Queue existing analyses whose root_cause matches a newly created rule."""
    unmatched = db.get_unmatched_analyses_by_root_cause(root_cause, pipeline_type_id)
    queued = 0
    for a in unmatched:
        db.queue_reanalysis(
            pipeline_run_id=a["pipeline_run_id"],
            pipeline_type_id=pipeline_type_id,
            reason=f"new_rule:{root_cause}",
            triggered_by="auto",
        )
        queued += 1
    if queued:
        logger.info(
            "[%s] Queued %d unmatched '%s' analyses for re-analysis",
            pipeline_type_id, queued, root_cause,
        )
