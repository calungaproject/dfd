"""DFD Collector — long-running service with internal scheduler.

Runs on a configurable interval (default 24h) and also polls the
collect_requests table for API-triggered runs.

Each run:
1. Query KubeArchive for pipeline runs
2. For new failed runs: download TaskRuns, logs, extract metadata
3. Persist artifacts to DB, store full PipelineRun JSON
4. Run multi-agent analysis on new failures
5. Process rule proposals + auto-consolidation
6. Process re-analysis queue
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import time

from dfd.analyzer.orchestrator import run_batch
from dfd.analyzer.reanalysis import process_reanalysis_queue
from dfd.collector.kubearchive import KubeArchiveClient
from dfd.common import claude_client, db, s3
from dfd.common.config import PipelineTypeConfig, Settings, load_pipeline_types
from dfd.common.models import ArtifactType, RunStatus
from dfd.common.taxonomy import consolidate_novel_root_causes, process_proposals

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("Received signal %d — shutting down after current run", signum)
    _shutdown = True


def main() -> None:
    """Entrypoint for the collector service."""
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    settings = Settings()
    db.init_pool(settings.database_url)
    claude_client.init_client(settings)
    s3.init_s3(settings.s3_endpoint_url or None)

    pipeline_types = load_pipeline_types()
    if not pipeline_types:
        logger.error("No pipeline types found in database — run migrations first")
        db.close_pool()
        return

    if settings.enabled_pipeline_types:
        enabled = settings.enabled_pipeline_types
    else:
        enabled = list(pipeline_types.keys())

    logger.info(
        "Collector started (interval=%dh, hours_back=%d, poll=%ds, types=%s)",
        settings.collect_interval_hours,
        settings.collect_hours_back,
        settings.collect_poll_interval_seconds,
        enabled,
    )

    try:
        _scheduler_loop(settings, pipeline_types, enabled)
    finally:
        db.close_pool()
        logger.info("Collector stopped")


def _scheduler_loop(
    settings: Settings,
    pipeline_types: dict[str, PipelineTypeConfig],
    enabled: list[str],
) -> None:
    """Main loop: run scheduled collection, then poll for API-triggered requests."""
    last_scheduled_run = 0.0

    while not _shutdown:
        now = time.time()
        interval_seconds = settings.collect_interval_hours * 3600

        # Check if it's time for a scheduled run
        if now - last_scheduled_run >= interval_seconds:
            logger.info("Starting scheduled collection run")
            _run_collection(
                settings,
                trigger="scheduled",
                hours_back=settings.collect_hours_back,
                pipeline_types_to_run=enabled,
                pipeline_types_config=pipeline_types,
            )
            last_scheduled_run = time.time()

        # Poll for API-triggered collect requests
        request = db.get_pending_collect_request()
        if request:
            req_id = request["id"]
            req_types = request.get("pipeline_types") or enabled
            req_hours = request.get("hours_back") or settings.collect_hours_back
            logger.info(
                "Processing collect request #%d (types=%s, hours_back=%d)",
                req_id,
                req_types,
                req_hours,
            )
            try:
                _run_collection(
                    settings,
                    trigger="api",
                    hours_back=req_hours,
                    pipeline_types_to_run=req_types,
                    pipeline_types_config=pipeline_types,
                    collect_request_id=req_id,
                )
                db.complete_collect_request(req_id)
            except Exception as e:
                logger.error("Collect request #%d failed: %s", req_id, e)
                db.fail_collect_request(req_id, str(e))

        # Sleep between polls
        for _ in range(settings.collect_poll_interval_seconds):
            if _shutdown:
                return
            time.sleep(1)


def _run_collection(
    settings: Settings,
    trigger: str,
    hours_back: int,
    pipeline_types_to_run: list[str],
    pipeline_types_config: dict[str, PipelineTypeConfig],
    collect_request_id: int | None = None,
) -> None:
    """Execute a single collection + analysis run."""

    run_id = db.create_analysis_run(
        trigger=trigger,
        hours_back=hours_back,
        pipeline_types=pipeline_types_to_run,
    )
    logger.info("Analysis run #%d started (trigger=%s, hours_back=%d)", run_id, trigger, hours_back)

    if collect_request_id is not None:
        db.complete_collect_request(collect_request_id, analysis_run_id=run_id)

    ka_client = KubeArchiveClient(
        base_url=settings.kubearchive_url,
        token=settings.kubearchive_token,
        verify_tls=settings.kubearchive_verify_tls,
    )

    namespaces = {
        pipeline_types_config[pt_id].namespace
        for pt_id in pipeline_types_to_run
        if pt_id in pipeline_types_config
    }
    for ns in sorted(namespaces):
        if not ka_client.check_access(ns):
            db.update_analysis_run(
                run_id, status="failed",
                error_message=f"KubeArchive access check failed for namespace {ns}",
            )
            logger.error(
                "KubeArchive access check failed for namespace %s — aborting run #%d",
                ns, run_id,
            )
            ka_client.close()
            return

    total_runs = 0
    failed_to_analyze: list[tuple[str, str, str | None]] = []

    for pt_id in pipeline_types_to_run:
        pt_config = pipeline_types_config.get(pt_id)
        if pt_config is None:
            logger.warning("Unknown pipeline type '%s' — skipping", pt_id)
            continue

        try:
            runs = ka_client.fetch_pipeline_runs(pt_config, hours_back)
        except Exception as e:
            logger.error("[%s] Failed to fetch pipeline runs: %s", pt_id, e)
            continue

        analyzed_ids = db.get_analyzed_pipeline_run_ids(pt_id)
        total_runs += len(runs)

        for run in runs:
            if not db.pipeline_run_exists(run.id):
                pr_json = ka_client.fetch_pipelinerun_json(run.id, namespace=run.namespace)
                db.insert_pipeline_run(run, pipelinerun_json=pr_json)

            if run.status == RunStatus.FAILED and run.id not in analyzed_ids:
                failed_to_analyze.append((run.id, pt_id, run.namespace))

    new_failures = len(failed_to_analyze)
    logger.info("Found %d total runs, %d new failures to analyze", total_runs, new_failures)

    db.update_analysis_run(run_id, status="collecting", total_pipeline_runs=total_runs)

    if new_failures == 0:
        logger.info("No new failures to analyze")
        db.update_analysis_run(run_id, status="completed")
        ka_client.close()
        return

    # Collect data for each new failure
    for pipeline_run_id, pt_id, ns in failed_to_analyze:
        _collect_failure_data(pipeline_run_id, pt_id, ka_client, namespace=ns)

    ka_client.close()

    # --- Analysis phase ---
    db.update_analysis_run(run_id, status="analyzing")
    logger.info("Analysis phase — %d failures to analyze", new_failures)

    analyzed_count, _ = asyncio.run(
        run_batch(failed_to_analyze, settings, run_id)
    )

    # Process rule proposals per pipeline type
    affected_types = {pt_id for _, pt_id, _ns in failed_to_analyze}
    for pt_id in affected_types:
        try:
            accepted = process_proposals(pt_id, run_id, settings.claude_model)
            if accepted:
                logger.info("[%s] %d new taxonomy rules accepted", pt_id, accepted)
        except Exception as e:
            logger.error("[%s] Proposal processing failed: %s", pt_id, e)

        try:
            promoted = consolidate_novel_root_causes(pt_id, run_id, settings.claude_model)
            if promoted:
                logger.info("[%s] %d novel root causes promoted", pt_id, promoted)
        except Exception as e:
            logger.error("[%s] Novel consolidation failed: %s", pt_id, e)

    # Process re-analysis queue
    try:
        reanalyzed = asyncio.run(
            process_reanalysis_queue(settings, run_id)
        )
        if reanalyzed:
            logger.info("Re-analyzed %d queued items", reanalyzed)
    except Exception as e:
        logger.error("Re-analysis queue processing failed: %s", e)

    total_cost = db.get_analysis_run_total_cost(run_id)
    db.update_analysis_run(
        run_id, status="completed", analyzed_count=analyzed_count, total_cost_usd=total_cost,
    )
    logger.info(
        "Analysis run #%d completed: %d/%d analyzed, cost=$%.4f",
        run_id, analyzed_count, new_failures, total_cost,
    )


def _collect_failure_data(
    pipeline_run_id: str,
    pipeline_type_id: str,
    ka_client: KubeArchiveClient,
    namespace: str,
) -> None:
    """Collect TaskRuns, metadata, and failed step log for a single failure."""
    logger.info("[%s] Collecting failure data...", pipeline_run_id)

    # 1. Fetch TaskRuns
    try:
        taskruns_data = ka_client.fetch_taskruns_json(pipeline_run_id, namespace=namespace)
    except Exception as e:
        logger.warning("[%s] Failed to fetch TaskRuns: %s", pipeline_run_id, e)
        taskruns_data = {"items": []}

    # 2. Extract metadata
    metadata = ka_client.extract_metadata(pipeline_run_id, pipeline_type_id, taskruns_data)

    # 3. Persist TaskRuns JSON as artifact
    taskruns_json_str = json.dumps(taskruns_data, default=str)
    db.insert_artifact(
        pipeline_run_id=pipeline_run_id,
        artifact_type=ArtifactType.TASKRUNS_JSON,
        filename="taskruns.json",
        content=taskruns_json_str,
        size_bytes=len(taskruns_json_str.encode()),
    )

    # 4. Persist metadata as artifact
    metadata_str = metadata.model_dump_json()
    db.insert_artifact(
        pipeline_run_id=pipeline_run_id,
        artifact_type=ArtifactType.METADATA_JSON,
        filename="metadata.json",
        content=metadata_str,
        size_bytes=len(metadata_str.encode()),
    )

    # 5. Fetch and persist failed step log
    failed_step_log = ka_client.fetch_failed_step_log(
        metadata.pod_name or "", metadata.failed_step or "", namespace=namespace,
    )

    if failed_step_log:
        db.insert_artifact(
            pipeline_run_id=pipeline_run_id,
            artifact_type=ArtifactType.FAILED_STEP_LOG,
            filename=f"step-{metadata.failed_step or 'unknown'}.log",
            content=failed_step_log,
            size_bytes=len(failed_step_log.encode()),
        )

    logger.info(
        "[%s] Data collection complete (task=%s, step=%s)",
        pipeline_run_id,
        metadata.failed_task or "?",
        metadata.failed_step or "?",
    )


if __name__ == "__main__":
    main()
