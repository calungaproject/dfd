"""Historical Analyst agent — cross-analysis comparison and validation."""

from __future__ import annotations

import logging

from dfd.analyzer import board
from dfd.analyzer.prompts import historical_analyst_prompt
from dfd.common import claude_client, db
from dfd.common.config import Settings
from dfd.common.models import InvocationType

logger = logging.getLogger(__name__)


def analyze(
    pipeline_run_id: str,
    pipeline_type_id: str,
    settings: Settings,
    analysis_run_id: int,
) -> None:
    """Run historical analysis and post findings to the investigation board."""
    board_md = board.get_board_as_markdown(pipeline_run_id)

    entries = db.get_board_entries(pipeline_run_id)
    suggested_root_cause = None
    for entry in entries:
        if entry.get("classification_suggestion"):
            suggested_root_cause = entry["classification_suggestion"]

    parts = [
        f"## Pipeline Run: `{pipeline_run_id}`\n",
        f"### Pipeline Type: `{pipeline_type_id}`\n",
        board_md,
    ]

    if suggested_root_cause and suggested_root_cause != "unknown":
        similar = db.get_recent_analyses(pipeline_type_id, suggested_root_cause, limit=10)
        if similar:
            parts.append(f"\n### Recent analyses with root_cause=`{suggested_root_cause}`\n")
            for a in similar:
                parts.append(
                    f"- `{a['pipeline_run_id']}` "
                    f"(confidence={a['confidence']}, "
                    f"error_message={a.get('error_message', 'N/A')[:100]})"
                )
            parts.append("")
        else:
            parts.append(
                f"\n### No previous analyses with root_cause=`{suggested_root_cause}` found.\n"
                "This appears to be a new classification.\n"
            )

    unknowns = db.get_recent_unknowns(pipeline_type_id, days=30, limit=5)
    if unknowns:
        parts.append("\n### Recent 'unknown' analyses\n")
        for u in unknowns:
            parts.append(
                f"- `{u['pipeline_run_id']}` "
                f"(error_message={u.get('error_message', 'N/A')[:100]})"
            )
        parts.append("")

    parts.append(
        "\nCompare the current failure against historical data. "
        "Validate the proposed classification, check for over-broad categories, "
        "and note any trends."
    )

    user_message = "\n".join(parts)

    response = claude_client.send_message(
        system=historical_analyst_prompt(),
        messages=[{"role": "user", "content": user_message}],
        model=settings.claude_model,
        max_tokens=8000,
        thinking_budget=settings.thinking_budget_tokens,
    )

    cost_entry = claude_client.make_cost_entry(
        response,
        model=settings.claude_model,
        invocation_type=InvocationType.ANALYSIS,
        analysis_run_id=analysis_run_id,
        pipeline_run_id=pipeline_run_id,
    )
    db.insert_cost_entry(cost_entry)

    board.post_findings(
        pipeline_run_id=pipeline_run_id,
        agent_type="historical_analyst",
        findings=response.text,
        thinking=response.thinking if response.thinking else None,
    )

    logger.info("[%s] Historical analyst complete (%d chars)", pipeline_run_id, len(response.text))
