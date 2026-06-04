"""Manager agent — initial investigation + final synthesis.

Runs twice per failure:
1. triage(): reads metadata + log, selects specialists via tool
2. synthesize(): reads board, produces final analysis via tool
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from dfd.analyzer import board
from dfd.analyzer.prompts import (
    PROPOSE_RULE_TOOL,
    SELECT_SPECIALISTS_TOOL,
    SUBMIT_ANALYSIS_TOOL,
    manager_synthesis_prompt,
    manager_triage_prompt,
)
from dfd.common import claude_client, db
from dfd.common.config import Settings
from dfd.common.models import AnalysisResult, ArtifactType, InvocationType, RuleProposal

logger = logging.getLogger(__name__)


@dataclass
class TriageResult:
    specialists: list[str] = field(default_factory=list)
    initial_classification: str = "unknown"
    confidence: str = "low"


@dataclass
class SynthesisResult:
    analysis: AnalysisResult | None = None
    rule_proposal: RuleProposal | None = None
    thinking: str = ""


def triage(
    pipeline_run_id: str,
    pipeline_type_id: str,
    settings: Settings,
    analysis_run_id: int,
) -> TriageResult:
    """Run the manager triage pass."""
    metadata_json = db.get_artifact(pipeline_run_id, ArtifactType.METADATA_JSON)
    failed_step_log = db.get_artifact(pipeline_run_id, ArtifactType.FAILED_STEP_LOG)

    parts = [f"## Pipeline Run: `{pipeline_run_id}`\n"]

    if metadata_json:
        parts.append(f"### Metadata\n```json\n{metadata_json}\n```\n")
    else:
        parts.append("### Metadata\nNo metadata available.\n")

    if failed_step_log:
        log_text = failed_step_log
        if len(log_text) > 50000:
            log_text = log_text[:25000] + "\n\n... [truncated] ...\n\n" + log_text[-25000:]
        parts.append(f"### Failed Step Log\n```\n{log_text}\n```\n")
    else:
        parts.append("### Failed Step Log\nNo log available.\n")

    user_message = "\n".join(parts)

    response = claude_client.send_message(
        system=manager_triage_prompt(pipeline_type_id),
        messages=[{"role": "user", "content": user_message}],
        model=settings.claude_model,
        tools=[SELECT_SPECIALISTS_TOOL],
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

    result = TriageResult()
    if response.tool_use:
        tool_input = response.tool_use[0].input
        result.specialists = tool_input.get("specialists", [])
        result.initial_classification = tool_input.get("initial_classification", "unknown")
        result.confidence = tool_input.get("confidence", "low")
    else:
        logger.warning(
            "[%s] Triage did not call select_specialists — defaulting to log_analyst",
            pipeline_run_id,
        )
        result.specialists = ["log_analyst"]

    board.post_findings(
        pipeline_run_id=pipeline_run_id,
        agent_type="manager_triage",
        findings=(
            f"Initial classification: `{result.initial_classification}` "
            f"(confidence: {result.confidence}). "
            f"Selected specialists: {result.specialists or ['none']}. "
            f"Reasoning: "
            f"{response.tool_use[0].input.get('reasoning', 'N/A') if response.tool_use else 'N/A'}"
        ),
        classification_suggestion=result.initial_classification,
        confidence=result.confidence,
        thinking=response.thinking if response.thinking else None,
    )

    logger.info(
        "[%s] Triage: classification=%s, confidence=%s, specialists=%s",
        pipeline_run_id, result.initial_classification, result.confidence, result.specialists,
    )

    return result


def synthesize(
    pipeline_run_id: str,
    pipeline_type_id: str,
    settings: Settings,
    analysis_run_id: int,
) -> SynthesisResult:
    """Run the manager synthesis pass."""
    board_md = board.get_board_as_markdown(pipeline_run_id)

    user_message = (
        f"## Pipeline Run: `{pipeline_run_id}`\n\n"
        f"{board_md}\n\n"
        "Review all investigation board entries above and submit your final analysis "
        "using the `submit_analysis` tool. If you've identified a new recurring failure "
        "pattern, also use the `propose_rule` tool."
    )

    response = claude_client.send_message(
        system=manager_synthesis_prompt(pipeline_type_id),
        messages=[{"role": "user", "content": user_message}],
        model=settings.claude_model,
        tools=[SUBMIT_ANALYSIS_TOOL, PROPOSE_RULE_TOOL],
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

    result = SynthesisResult(thinking=response.thinking)

    for tool in response.tool_use:
        if tool.name == "submit_analysis":
            result.analysis = AnalysisResult(**tool.input)
        elif tool.name == "propose_rule":
            result.rule_proposal = RuleProposal(
                pipeline_type_id=pipeline_type_id,
                pipeline_run_id=pipeline_run_id,
                **tool.input,
            )

    if result.analysis is None:
        logger.warning(
            "[%s] Synthesis did not produce an analysis (stop_reason=%s)",
            pipeline_run_id, response.stop_reason,
        )
        if response.text:
            logger.info("[%s] Manager text: %s", pipeline_run_id, response.text[:200])

    return result
