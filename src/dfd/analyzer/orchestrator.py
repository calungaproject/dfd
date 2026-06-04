"""Per-failure orchestration — coordinates the multi-agent analysis pipeline.

Flow per failure:
1. Clear board
2. Manager triage -> selects specialists
3. Selected specialists run in parallel
4. Manager synthesis -> final analysis
5. Write to DB + upload conversation log to S3
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable

from dfd.analyzer import board
from dfd.analyzer.agents import historical_analyst, log_analyst, manager
from dfd.common import db, s3
from dfd.common.config import Settings

logger = logging.getLogger(__name__)

SPECIALIST_DISPATCH: dict[str, Callable] = {
    "log_analyst": log_analyst.analyze,
    "historical_analyst": historical_analyst.analyze,
}


async def analyze_failure(
    pipeline_run_id: str,
    pipeline_type_id: str,
    settings: Settings,
    analysis_run_id: int,
) -> bool:
    """Orchestrate multi-agent analysis for a single failed pipeline run."""
    logger.info("[%s] Starting multi-agent analysis", pipeline_run_id)

    conversation_log: list[dict] = []

    try:
        board.clear(pipeline_run_id)

        # Manager triage
        triage_result = await asyncio.to_thread(
            manager.triage, pipeline_run_id, pipeline_type_id, settings, analysis_run_id,
        )
        conversation_log.append({
            "agent": "manager_triage",
            "classification": triage_result.initial_classification,
            "confidence": triage_result.confidence,
            "specialists": triage_result.specialists,
        })

        # Run selected specialists in parallel
        if triage_result.specialists:
            specialist_tasks = []
            for spec_name in triage_result.specialists:
                spec_fn = SPECIALIST_DISPATCH.get(spec_name)
                if spec_fn is None:
                    logger.warning("[%s] Unknown specialist: %s", pipeline_run_id, spec_name)
                    continue

                if spec_name == "historical_analyst":
                    task = asyncio.to_thread(
                        spec_fn, pipeline_run_id, pipeline_type_id, settings, analysis_run_id,
                    )
                else:
                    task = asyncio.to_thread(
                        spec_fn, pipeline_run_id, settings, analysis_run_id,
                    )
                specialist_tasks.append((spec_name, task))

            if specialist_tasks:
                results = await asyncio.gather(
                    *(task for _, task in specialist_tasks),
                    return_exceptions=True,
                )
                for (spec_name, _), result in zip(specialist_tasks, results):
                    if isinstance(result, Exception):
                        logger.error(
                            "[%s] Specialist %s failed: %s", pipeline_run_id, spec_name, result,
                        )
                        board.post_findings(
                            pipeline_run_id=pipeline_run_id,
                            agent_type=spec_name,
                            findings=f"Agent failed with error: {result}",
                            confidence="low",
                            flags="agent_error",
                        )
                    conversation_log.append({
                        "agent": spec_name,
                        "completed": not isinstance(result, Exception),
                    })

        # Manager synthesis
        synthesis = await asyncio.to_thread(
            manager.synthesize, pipeline_run_id, pipeline_type_id, settings, analysis_run_id,
        )

        if synthesis.analysis is None:
            logger.error("[%s] Manager synthesis produced no analysis", pipeline_run_id)
            return False

        synthesis.analysis.taxonomy_matched = db.check_taxonomy_match(
            synthesis.analysis.root_cause, pipeline_type_id
        )
        if not synthesis.analysis.taxonomy_matched:
            logger.info(
                "[%s] Novel classification: %s", pipeline_run_id, synthesis.analysis.root_cause,
            )

        version = db.get_latest_analysis_version(pipeline_run_id) + 1
        analysis_id = db.insert_analysis(
            pipeline_run_id=pipeline_run_id,
            result=synthesis.analysis,
            thinking=synthesis.thinking,
            version=version,
        )

        logger.info(
            "[%s] Analysis written: id=%d, version=%d, root_cause=%s, confidence=%d",
            pipeline_run_id, analysis_id, version,
            synthesis.analysis.root_cause, synthesis.analysis.confidence,
        )

        conversation_log.append({
            "agent": "manager_synthesis",
            "root_cause": synthesis.analysis.root_cause,
            "category": synthesis.analysis.category,
            "confidence": synthesis.analysis.confidence,
        })

        # Upload conversation log to S3
        _upload_conversation_log(
            pipeline_run_id, version, conversation_log, settings,
        )

        # Store rule proposal if any
        if synthesis.rule_proposal:
            proposal_id = db.insert_rule_proposal(synthesis.rule_proposal)
            logger.info(
                "[%s] Rule proposal stored: id=%d, root_cause=%s",
                pipeline_run_id, proposal_id, synthesis.rule_proposal.root_cause,
            )

        return True

    except Exception as e:
        logger.exception("[%s] Analysis failed: %s", pipeline_run_id, e)
        return False


def _upload_conversation_log(
    pipeline_run_id: str,
    analysis_version: int,
    conversation_log: list[dict],
    settings: Settings,
) -> None:
    """Upload full conversation log to S3 and store pointer in DB."""
    # Include board entries in the log
    board_entries = db.get_board_entries(pipeline_run_id)
    full_log = {
        "pipeline_run_id": pipeline_run_id,
        "analysis_version": analysis_version,
        "agents": conversation_log,
        "board_entries": board_entries,
    }

    s3_key = f"conversations/{pipeline_run_id}/v{analysis_version}.json"

    try:
        if s3.write_json(settings.s3_bucket, s3_key, full_log):
            agent_sequence = [entry["agent"] for entry in conversation_log]
            db.insert_conversation_log(
                pipeline_run_id=pipeline_run_id,
                analysis_version=analysis_version,
                s3_key=s3_key,
                summary=json.dumps({"agents": agent_sequence}),
                agent_sequence=agent_sequence,
            )
    except Exception as e:
        logger.warning("[%s] Failed to upload conversation log: %s", pipeline_run_id, e)


async def run_batch(
    failures: list[tuple[str, str, str | None]],
    settings: Settings,
    analysis_run_id: int,
) -> tuple[int, float]:
    """Run analysis on a batch of failures with bounded concurrency."""
    semaphore = asyncio.Semaphore(settings.max_parallel_specialists)
    analyzed_count = 0

    async def _analyze_with_semaphore(pipeline_run_id: str, pipeline_type_id: str) -> bool:
        async with semaphore:
            return await analyze_failure(
                pipeline_run_id, pipeline_type_id, settings, analysis_run_id,
            )

    tasks = [
        _analyze_with_semaphore(pr_id, pt_id)
        for pr_id, pt_id, _ in failures
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for (pr_id, _, _ns), result in zip(failures, results):
        if isinstance(result, Exception):
            logger.error("Batch analysis error for %s: %s", pr_id, result)
        elif result:
            analyzed_count += 1

    logger.info("Batch analysis complete: %d/%d succeeded", analyzed_count, len(failures))
    return analyzed_count, 0.0
