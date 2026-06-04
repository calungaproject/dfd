"""Chatbot tool definitions and handlers.

Each tool is defined as an Anthropic tool schema + a handler function that
executes DB queries or S3 reads and returns a text result.
"""

from __future__ import annotations

from typing import Any

from dfd.common import db, s3
from dfd.common.models import ArtifactType

CHATBOT_TOOLS: list[dict[str, Any]] = [
    {
        "name": "query_pipeline_runs",
        "description": (
            "Search pipeline runs by pipeline_type, status, package, "
            "date range, or root_cause."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline_type": {
                    "type": "string",
                    "enum": ["build", "integration_test", "enterprise_contract", "release"],
                },
                "status": {
                    "type": "string",
                    "enum": ["succeeded", "failed", "aborted"],
                },
                "package_name": {"type": "string"},
                "days": {"type": "integer"},
                "root_cause": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": [],
        },
    },
    {
        "name": "get_analysis_details",
        "description": (
            "Get the full analysis for a specific pipeline run, including "
            "evidence, details, confidence, and alternatives."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline_run_id": {"type": "string"},
            },
            "required": ["pipeline_run_id"],
        },
    },
    {
        "name": "read_artifact",
        "description": (
            "Read a key artifact: failed_step_log, taskruns_json, "
            "or metadata_json."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline_run_id": {"type": "string"},
                "artifact_type": {
                    "type": "string",
                    "enum": [
                        "failed_step_log",
                        "taskruns_json",
                        "metadata_json",
                    ],
                },
            },
            "required": ["pipeline_run_id", "artifact_type"],
        },
    },
    {
        "name": "get_investigation_board",
        "description": (
            "Get the full investigation board for a pipeline run — all "
            "agent findings, thinking, and classification suggestions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline_run_id": {"type": "string"},
            },
            "required": ["pipeline_run_id"],
        },
    },
    {
        "name": "get_conversation_log",
        "description": (
            "Get the full agent conversation log from S3 for a "
            "pipeline run — complete multi-agent reasoning chain."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline_run_id": {"type": "string"},
            },
            "required": ["pipeline_run_id"],
        },
    },
    {
        "name": "get_statistics",
        "description": (
            "Get aggregated statistics: pass rates, failure trends, "
            "root cause distribution."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline_type": {
                    "type": "string",
                    "enum": ["build", "integration_test", "enterprise_contract", "release"],
                },
                "days": {"type": "integer", "default": 30},
            },
            "required": [],
        },
    },
    {
        "name": "get_taxonomy_rules",
        "description": (
            "Get current taxonomy rules for a pipeline type. Returns "
            "rule IDs needed for update/delete/merge."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline_type_id": {"type": "string"},
            },
            "required": ["pipeline_type_id"],
        },
    },
    {
        "name": "get_analysis_history",
        "description": (
            "Get all analysis versions for a pipeline run — shows how "
            "classification evolved over time."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline_run_id": {"type": "string"},
            },
            "required": ["pipeline_run_id"],
        },
    },
    {
        "name": "get_pending_proposals",
        "description": (
            "Get pending taxonomy rule proposals for a pipeline type."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline_type_id": {"type": "string"},
            },
            "required": ["pipeline_type_id"],
        },
    },
    {
        "name": "update_taxonomy_rule",
        "description": (
            "Update an existing taxonomy rule. Call with confirmed=false "
            "first to preview, then confirmed=true to execute."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline_type_id": {"type": "string"},
                "rule_id": {"type": "integer"},
                "root_cause": {"type": "string"},
                "category": {
                    "type": "string",
                    "enum": ["build", "infra", "unknown"],
                },
                "error_signature": {"type": "string"},
                "priority_rule": {"type": "string"},
                "investigation_recipe": {"type": "string"},
                "confirmed": {"type": "boolean", "default": False},
            },
            "required": ["pipeline_type_id", "rule_id"],
        },
    },
    {
        "name": "delete_taxonomy_rule",
        "description": (
            "Delete a taxonomy rule. Call with confirmed=false first "
            "to preview, then confirmed=true to execute."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline_type_id": {"type": "string"},
                "rule_id": {"type": "integer"},
                "confirmed": {"type": "boolean", "default": False},
            },
            "required": ["pipeline_type_id", "rule_id"],
        },
    },
    {
        "name": "merge_taxonomy_rules",
        "description": (
            "Merge one taxonomy rule into another. Call with "
            "confirmed=false first to preview."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline_type_id": {"type": "string"},
                "source_rule_id": {"type": "integer"},
                "target_rule_id": {"type": "integer"},
                "confirmed": {"type": "boolean", "default": False},
            },
            "required": [
                "pipeline_type_id",
                "source_rule_id",
                "target_rule_id",
            ],
        },
    },
    {
        "name": "accept_proposal",
        "description": (
            "Accept a pending taxonomy rule proposal. Call with "
            "confirmed=false first to preview."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline_type_id": {"type": "string"},
                "proposal_id": {"type": "integer"},
                "confirmed": {"type": "boolean", "default": False},
            },
            "required": ["pipeline_type_id", "proposal_id"],
        },
    },
    {
        "name": "reject_proposal",
        "description": (
            "Reject a pending taxonomy rule proposal. Call with "
            "confirmed=false first to preview."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline_type_id": {"type": "string"},
                "proposal_id": {"type": "integer"},
                "confirmed": {"type": "boolean", "default": False},
            },
            "required": ["pipeline_type_id", "proposal_id"],
        },
    },
]


def execute_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    settings: Any,
) -> str:
    """Execute a chatbot tool and return the result as text."""
    handler = _HANDLERS.get(tool_name)
    if not handler:
        return f"Unknown tool: {tool_name}"
    try:
        return handler(tool_input, settings)
    except Exception as e:
        return f"Tool error ({tool_name}): {e}"


def _query_pipeline_runs(inp: dict, settings: Any) -> str:
    runs, total, _counts = db.get_pipeline_runs(
        pipeline_type_id=inp.get("pipeline_type"),
        status=inp.get("status"),
        package_name=inp.get("package_name"),
        days=inp.get("days"),
        root_cause=inp.get("root_cause"),
        per_page=inp.get("limit", 20),
    )
    if not runs:
        return "No pipeline runs found matching the criteria."

    lines = [f"Found {total} pipeline runs (showing {len(runs)}):"]
    for r in runs:
        line = f"- {r['id']} [{r.get('status', '?')}]"
        if r.get("root_cause"):
            line += f" root_cause={r['root_cause']}"
        if r.get("confidence") is not None:
            line += f" confidence={r['confidence']}%"
        if r.get("package_name"):
            line += f" pkg={r['package_name']}"
        line += f" ({r.get('completion_time', '?')})"
        lines.append(line)
    return "\n".join(lines)


def _get_analysis_details(inp: dict, settings: Any) -> str:
    run = db.get_pipeline_run_detail(inp["pipeline_run_id"])
    if not run:
        return f"Pipeline run {inp['pipeline_run_id']} not found."

    parts = [
        f"Pipeline run: {run['id']}",
        f"Status: {run.get('status')}",
        f"Pipeline type: {run.get('pipeline_type_id')}",
        f"Package: {run.get('package_name', 'N/A')}",
        f"Completion: {run.get('completion_time')}",
    ]

    if run.get("root_cause"):
        parts.append(f"\nRoot cause: {run['root_cause']}")
        parts.append(f"Category: {run.get('category')}")
        parts.append(f"Confidence: {run.get('confidence')}%")
        if run.get("alternative_root_cause"):
            parts.append(
                f"Alternative: {run['alternative_root_cause']} "
                f"({run.get('alternative_confidence')}%)"
            )
        if run.get("ambiguity_note"):
            parts.append(f"Ambiguity: {run['ambiguity_note']}")
        parts.append(f"\nFailed task: {run.get('failed_task')}")
        parts.append(f"Failed step: {run.get('failed_step')}")
        parts.append(f"Error: {run.get('error_message')}")
        if run.get("evidence"):
            parts.append(f"\nEvidence:\n{run['evidence']}")
        if run.get("details"):
            parts.append(f"\nDetails: {run['details']}")
        if run.get("suggested_action"):
            parts.append(
                f"\nSuggested action: {run['suggested_action']}"
            )
    else:
        parts.append("\nNo analysis available for this run.")

    return "\n".join(parts)


def _read_artifact(inp: dict, settings: Any) -> str:
    artifact_type = ArtifactType(inp["artifact_type"])
    content = db.get_artifact(inp["pipeline_run_id"], artifact_type)
    if content is None:
        return (
            f"No {inp['artifact_type']} artifact found for "
            f"{inp['pipeline_run_id']}."
        )
    if len(content) > 50000:
        content = (
            content[:25000]
            + "\n\n... [truncated] ...\n\n"
            + content[-25000:]
        )
    return content


def _get_investigation_board(inp: dict, settings: Any) -> str:
    entries = db.get_board_entries(inp["pipeline_run_id"])
    if not entries:
        return (
            f"No investigation board entries for "
            f"{inp['pipeline_run_id']}."
        )

    lines = [
        f"Investigation board for {inp['pipeline_run_id']} "
        f"({len(entries)} entries):"
    ]
    for i, entry in enumerate(entries, 1):
        lines.append(
            f"\n--- Entry {i}: {entry['agent_type']} ---"
        )
        lines.append(f"Findings: {entry['findings']}")
        if entry.get("evidence"):
            lines.append(f"Evidence: {entry['evidence'][:500]}")
        if entry.get("classification_suggestion"):
            lines.append(
                f"Classification: "
                f"{entry['classification_suggestion']} "
                f"(confidence: {entry.get('confidence', '?')})"
            )
    return "\n".join(lines)


def _get_conversation_log(inp: dict, settings: Any) -> str:
    log = db.get_conversation_log(inp["pipeline_run_id"])
    if not log:
        return (
            f"No conversation log found for "
            f"{inp['pipeline_run_id']}."
        )

    import json
    full_log = s3.read_json(settings.s3_bucket, log["s3_key"])
    if full_log is None:
        return "Conversation log not found in S3."

    return json.dumps(full_log, indent=2, default=str)[:50000]


def _get_statistics(inp: dict, settings: Any) -> str:
    stats = db.get_stats(
        pipeline_type_id=inp.get("pipeline_type"),
        days=inp.get("days", 30),
    )

    lines = [
        f"Statistics (last {inp.get('days', 30)} days):",
        f"Total runs: {stats['total']}",
        f"Succeeded: {stats['succeeded']}",
        f"Failed: {stats['failed']}",
        f"Aborted: {stats['aborted']}",
        f"Pass rate: {stats['pass_rate']}%",
    ]

    if stats.get("root_causes"):
        lines.append("\nFailure breakdown:")
        for rc in stats["root_causes"]:
            lines.append(
                f"  {rc['root_cause']}: {rc['count']} "
                f"({rc.get('category', '?')})"
            )

    return "\n".join(lines)


def _get_taxonomy_rules(inp: dict, settings: Any) -> str:
    rules = db.get_taxonomy_rules(inp["pipeline_type_id"])
    if not rules:
        return f"No taxonomy rules for {inp['pipeline_type_id']}."

    lines = [
        f"Taxonomy rules for {inp['pipeline_type_id']} "
        f"({len(rules)} rules):"
    ]
    for r in rules:
        lines.append(
            f"  #{r['id']} [{r['priority_order']}] "
            f"{r['root_cause']} ({r['category']}): "
            f"{r['error_signature']}"
        )
        if r.get("priority_rule"):
            lines.append(f"     Rule: {r['priority_rule']}")
    return "\n".join(lines)


def _get_analysis_history(inp: dict, settings: Any) -> str:
    history = db.get_analysis_history(inp["pipeline_run_id"])
    if not history:
        return (
            f"No analysis history for {inp['pipeline_run_id']}."
        )

    lines = [
        f"Analysis history for {inp['pipeline_run_id']} "
        f"({len(history)} versions):"
    ]
    for h in history:
        lines.append(
            f"  v{h['analysis_version']}: {h['root_cause']} "
            f"({h['category']}) confidence={h['confidence']}% "
            f"at {h.get('created_at', '?')}"
        )
    return "\n".join(lines)


def _get_pending_proposals(inp: dict, settings: Any) -> str:
    proposals = db.get_pending_proposals(inp["pipeline_type_id"])
    if not proposals:
        return (
            f"No pending proposals for {inp['pipeline_type_id']}."
        )

    lines = [
        f"Pending proposals for {inp['pipeline_type_id']} "
        f"({len(proposals)}):"
    ]
    for p in proposals:
        lines.append(
            f"  #{p['id']}: {p['root_cause']} ({p['category']})"
        )
        lines.append(f"     Signature: {p['error_signature']}")
        if p.get("reasoning"):
            lines.append(f"     Reasoning: {p['reasoning']}")
    return "\n".join(lines)


def _update_taxonomy_rule(inp: dict, settings: Any) -> str:
    pt_id = inp["pipeline_type_id"]
    rule_id = inp["rule_id"]

    rules = db.get_taxonomy_rules(pt_id)
    rule = next((r for r in rules if r["id"] == rule_id), None)
    if not rule:
        return f"Rule #{rule_id} not found for {pt_id}."

    old_root_cause = rule["root_cause"]
    changes: list[str] = []
    for field in (
        "root_cause", "category", "error_signature",
        "priority_rule", "investigation_recipe",
    ):
        if field in inp and inp[field] is not None:
            changes.append(
                f"  {field}: {rule.get(field, '')!r} -> {inp[field]!r}"
            )

    if not changes:
        return "No fields to update."

    affected = db.get_recent_analyses(
        pt_id, old_root_cause, days=90, limit=50
    )

    if not inp.get("confirmed"):
        return (
            f"PREVIEW - update rule #{rule_id} ({old_root_cause}) "
            f"on {pt_id}:\n"
            + "\n".join(changes)
            + f"\n\n{len(affected)} analyses will be queued for "
            "re-analysis.\n"
            "Ask the user to confirm before calling with "
            "confirmed=true."
        )

    db.update_taxonomy_rule(
        rule_id,
        root_cause=inp.get("root_cause"),
        category=inp.get("category"),
        error_signature=inp.get("error_signature"),
        priority_rule=inp.get("priority_rule"),
        investigation_recipe=inp.get("investigation_recipe"),
    )

    for a in affected:
        db.queue_reanalysis(
            pipeline_run_id=a["pipeline_run_id"],
            pipeline_type_id=pt_id,
            reason=f"rule_updated:{old_root_cause}",
            triggered_by="chat",
        )

    return (
        f"Rule #{rule_id} updated.\n"
        f"Queued {len(affected)} analyses for re-analysis."
    )


def _delete_taxonomy_rule(inp: dict, settings: Any) -> str:
    pt_id = inp["pipeline_type_id"]
    rule_id = inp["rule_id"]

    rules = db.get_taxonomy_rules(pt_id)
    rule = next((r for r in rules if r["id"] == rule_id), None)
    if not rule:
        return f"Rule #{rule_id} not found for {pt_id}."

    root_cause = rule["root_cause"]
    affected = db.get_recent_analyses(
        pt_id, root_cause, days=90, limit=50
    )

    if not inp.get("confirmed"):
        return (
            f"PREVIEW - delete rule #{rule_id} ({root_cause}) "
            f"from {pt_id}:\n"
            f"  Category: {rule.get('category')}\n"
            f"  Error signature: {rule.get('error_signature')}\n\n"
            f"{len(affected)} analyses will be queued for "
            "re-analysis.\n"
            "Ask the user to confirm before calling with "
            "confirmed=true."
        )

    db.delete_taxonomy_rule(rule_id)
    for a in affected:
        db.queue_reanalysis(
            pipeline_run_id=a["pipeline_run_id"],
            pipeline_type_id=pt_id,
            reason=f"rule_deleted:{root_cause}",
            triggered_by="chat",
        )

    return (
        f"Rule #{rule_id} ({root_cause}) deleted.\n"
        f"Queued {len(affected)} analyses for re-analysis."
    )


def _merge_taxonomy_rules(inp: dict, settings: Any) -> str:
    pt_id = inp["pipeline_type_id"]
    source_id = inp["source_rule_id"]
    target_id = inp["target_rule_id"]

    if source_id == target_id:
        return "Cannot merge a rule into itself."

    rules = db.get_taxonomy_rules(pt_id)
    source = next(
        (r for r in rules if r["id"] == source_id), None
    )
    target = next(
        (r for r in rules if r["id"] == target_id), None
    )

    if not source:
        return f"Source rule #{source_id} not found for {pt_id}."
    if not target:
        return f"Target rule #{target_id} not found for {pt_id}."

    if not inp.get("confirmed"):
        return (
            f"PREVIEW - merge rule #{source_id} "
            f"({source['root_cause']}) INTO #{target_id} "
            f"({target['root_cause']}) on {pt_id}:\n"
            "  Source will be DELETED, all its analyses relabeled "
            "to target.\n"
            "Ask the user to confirm."
        )

    relabeled = db.relabel_analyses(
        source["root_cause"], target["root_cause"], pt_id
    )
    db.delete_taxonomy_rule(source_id)

    return (
        f"Merged #{source_id} ({source['root_cause']}) into "
        f"#{target_id} ({target['root_cause']}).\n"
        f"Relabeled {relabeled} analyses."
    )


def _accept_proposal(inp: dict, settings: Any) -> str:
    pt_id = inp["pipeline_type_id"]
    proposal_id = inp["proposal_id"]

    proposals = db.get_pending_proposals(pt_id)
    proposal = next(
        (p for p in proposals if p["id"] == proposal_id), None
    )
    if not proposal:
        return (
            f"Proposal #{proposal_id} not found or not pending "
            f"for {pt_id}."
        )

    if not inp.get("confirmed"):
        unknowns = db.get_recent_unknowns(pt_id, days=90, limit=100)
        return (
            f"PREVIEW - accept proposal #{proposal_id} for "
            f"{pt_id}:\n"
            f"  Root cause: {proposal['root_cause']}\n"
            f"  Category: {proposal['category']}\n"
            f"  Error signature: {proposal['error_signature']}\n\n"
            f"{len(unknowns)} unknown failures will be queued for "
            "re-analysis.\n"
            "Ask the user to confirm."
        )

    existing = db.get_taxonomy_rules(pt_id)
    next_priority = (
        max((r["priority_order"] for r in existing), default=0) + 1
    )

    rule_id = db.insert_taxonomy_rule(
        pipeline_type_id=pt_id,
        root_cause=proposal["root_cause"],
        category=proposal["category"],
        error_signature=proposal["error_signature"],
        priority_order=next_priority,
        priority_rule=proposal.get("priority_rule"),
        investigation_recipe=proposal.get("investigation_recipe"),
        origin="agent_proposed_reviewed",
    )

    if rule_id == -1:
        return (
            f"A rule with root_cause '{proposal['root_cause']}' "
            f"already exists for {pt_id}."
        )

    db.update_proposal_status(proposal_id, "accepted")

    unknowns = db.get_recent_unknowns(pt_id, days=90, limit=100)
    for u in unknowns:
        db.queue_reanalysis(
            pipeline_run_id=u["pipeline_run_id"],
            pipeline_type_id=pt_id,
            reason=f"rule_accepted:{proposal['root_cause']}",
            triggered_by="chat",
        )

    return (
        f"Proposal #{proposal_id} accepted. Created rule "
        f"#{rule_id} ({proposal['root_cause']}).\n"
        f"Queued {len(unknowns)} unknowns for re-analysis."
    )


def _reject_proposal(inp: dict, settings: Any) -> str:
    pt_id = inp["pipeline_type_id"]
    proposal_id = inp["proposal_id"]

    proposals = db.get_pending_proposals(pt_id)
    proposal = next(
        (p for p in proposals if p["id"] == proposal_id), None
    )
    if not proposal:
        return (
            f"Proposal #{proposal_id} not found or not pending "
            f"for {pt_id}."
        )

    if not inp.get("confirmed"):
        return (
            f"PREVIEW - reject proposal #{proposal_id} for "
            f"{pt_id}:\n"
            f"  Root cause: {proposal['root_cause']}\n"
            f"  Category: {proposal['category']}\n"
            f"  Reasoning: {proposal.get('reasoning', '(none)')}\n"
            "Ask the user to confirm."
        )

    db.update_proposal_status(proposal_id, "rejected")
    return f"Proposal #{proposal_id} ({proposal['root_cause']}) rejected."


_HANDLERS = {
    "query_pipeline_runs": _query_pipeline_runs,
    "get_analysis_details": _get_analysis_details,
    "read_artifact": _read_artifact,
    "get_investigation_board": _get_investigation_board,
    "get_conversation_log": _get_conversation_log,
    "get_statistics": _get_statistics,
    "get_taxonomy_rules": _get_taxonomy_rules,
    "get_analysis_history": _get_analysis_history,
    "get_pending_proposals": _get_pending_proposals,
    "update_taxonomy_rule": _update_taxonomy_rule,
    "delete_taxonomy_rule": _delete_taxonomy_rule,
    "merge_taxonomy_rules": _merge_taxonomy_rules,
    "accept_proposal": _accept_proposal,
    "reject_proposal": _reject_proposal,
}
