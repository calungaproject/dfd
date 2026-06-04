"""Re-analysis queue processor.

When new taxonomy rules are accepted, previously-classified "unknown"
failures are queued for re-analysis with the updated taxonomy.
"""

from __future__ import annotations

import asyncio
import logging

from dfd.analyzer.orchestrator import analyze_failure
from dfd.common import db
from dfd.common.config import Settings

logger = logging.getLogger(__name__)


async def process_reanalysis_queue(
    settings: Settings,
    analysis_run_id: int,
    max_items: int = 20,
) -> int:
    """Process pending re-analysis items. Returns the count of successfully re-analyzed."""
    pending = db.get_pending_reanalysis()
    if not pending:
        return 0

    if len(pending) > max_items:
        logger.info(
            "Re-analysis queue has %d items, processing first %d", len(pending), max_items,
        )
        pending = pending[:max_items]

    logger.info("Processing %d re-analysis items", len(pending))

    reanalyzed = 0
    semaphore = asyncio.Semaphore(settings.max_parallel_specialists)

    async def _reanalyze(item: dict) -> tuple[int, bool]:
        queue_id = item["id"]
        pipeline_run_id = item["pipeline_run_id"]
        pipeline_type_id = item["pipeline_type_id"]

        db.update_reanalysis_status(queue_id, "in_progress")
        try:
            async with semaphore:
                success = await analyze_failure(
                    pipeline_run_id, pipeline_type_id, settings, analysis_run_id,
                )
            db.update_reanalysis_status(queue_id, "completed" if success else "skipped")
            return queue_id, success
        except Exception as e:
            logger.error("[%s] Re-analysis failed: %s", pipeline_run_id, e)
            db.update_reanalysis_status(queue_id, "skipped")
            return queue_id, False

    tasks = [_reanalyze(item) for item in pending]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            logger.error("Re-analysis task error: %s", result)
        elif result[1]:
            reanalyzed += 1

    logger.info("Re-analysis complete: %d/%d succeeded", reanalyzed, len(pending))
    return reanalyzed
