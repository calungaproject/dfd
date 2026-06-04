"""Log Analyst agent — deep analysis of pipeline failure logs."""

from __future__ import annotations

import logging

from dfd.analyzer import board
from dfd.analyzer.prompts import log_analyst_prompt
from dfd.common import claude_client, db
from dfd.common.config import Settings
from dfd.common.models import ArtifactType, InvocationType

logger = logging.getLogger(__name__)


def analyze(
    pipeline_run_id: str,
    settings: Settings,
    analysis_run_id: int,
) -> None:
    """Run log analysis and post findings to the investigation board."""
    failed_step_log = db.get_artifact(pipeline_run_id, ArtifactType.FAILED_STEP_LOG)
    taskruns_json = db.get_artifact(pipeline_run_id, ArtifactType.TASKRUNS_JSON)

    if not failed_step_log and not taskruns_json:
        board.post_findings(
            pipeline_run_id=pipeline_run_id,
            agent_type="log_analyst",
            findings="No log or taskrun data available for analysis.",
            confidence="low",
        )
        return

    parts = [f"## Pipeline Run: `{pipeline_run_id}`\n"]

    if failed_step_log:
        log_text = failed_step_log
        if len(log_text) > 80000:
            log_text = log_text[:40000] + "\n\n... [truncated] ...\n\n" + log_text[-40000:]
        parts.append(f"### Failed Step Log\n```\n{log_text}\n```\n")

    if taskruns_json:
        tr_text = taskruns_json
        if len(tr_text) > 30000:
            tr_text = tr_text[:15000] + "\n\n... [truncated] ...\n\n" + tr_text[-15000:]
        parts.append(f"### TaskRuns JSON\n```json\n{tr_text}\n```\n")

    parts.append(
        "\nAnalyze the logs above. Identify error patterns, failure root cause, "
        "and relevant log lines. Post your analysis as detailed findings."
    )

    user_message = "\n".join(parts)

    response = claude_client.send_message(
        system=log_analyst_prompt(),
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
        agent_type="log_analyst",
        findings=response.text,
        thinking=response.thinking if response.thinking else None,
    )

    logger.info("[%s] Log analyst complete (%d chars)", pipeline_run_id, len(response.text))
