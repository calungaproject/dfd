"""Investigation board — shared workspace for multi-agent collaboration."""

from __future__ import annotations

from dfd.common import db
from dfd.common.models import BoardEntry


def post_findings(
    pipeline_run_id: str,
    agent_type: str,
    findings: str,
    evidence: str | None = None,
    classification_suggestion: str | None = None,
    confidence: str | None = None,
    flags: str | None = None,
    thinking: str | None = None,
) -> int:
    entry = BoardEntry(
        agent_type=agent_type,
        findings=findings,
        evidence=evidence,
        classification_suggestion=classification_suggestion,
        confidence=confidence,
        flags=flags,
        thinking=thinking,
    )
    return db.post_to_board(pipeline_run_id, entry)


def get_board_as_markdown(pipeline_run_id: str) -> str:
    entries = db.get_board_entries(pipeline_run_id)

    if not entries:
        return "## Investigation Board\n\nNo entries yet.\n"

    lines = ["## Investigation Board", ""]

    for i, entry in enumerate(entries, 1):
        lines.append(f"### Entry {i}: {entry['agent_type']}")
        lines.append("")
        lines.append(f"**Findings:** {entry['findings']}")

        if entry.get("evidence"):
            lines.append(f"\n**Evidence:**\n```\n{entry['evidence']}\n```")

        if entry.get("classification_suggestion"):
            lines.append(
                f"\n**Classification suggestion:** `{entry['classification_suggestion']}`"
                f" (confidence: {entry.get('confidence', 'N/A')})"
            )

        if entry.get("flags"):
            lines.append(f"\n**Flags:** {entry['flags']}")

        lines.append("")

    return "\n".join(lines)


def clear(pipeline_run_id: str) -> None:
    db.clear_board(pipeline_run_id)
