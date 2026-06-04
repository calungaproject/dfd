"""PostgreSQL database layer for DFD.

Provides a connection pool and query helpers for all DFD tables.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extras
import psycopg2.pool

from dfd.common.models import (
    AnalysisResult,
    ArtifactType,
    BoardEntry,
    CostEntry,
    PipelineRunRecord,
    RuleProposal,
)

logger = logging.getLogger(__name__)

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def init_pool(database_url: str, minconn: int = 2, maxconn: int = 10) -> None:
    global _pool
    if _pool is not None:
        return
    _pool = psycopg2.pool.ThreadedConnectionPool(minconn, maxconn, database_url)
    logger.info("Database connection pool initialized")


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


@contextmanager
def get_conn():
    if _pool is None:
        raise RuntimeError("Database pool not initialized — call init_pool() first")
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


# ============================================================================
# Pipeline Runs
# ============================================================================


def pipeline_run_exists(pipeline_run_id: str) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pipeline_runs WHERE id = %s", (pipeline_run_id,))
            return cur.fetchone() is not None


def insert_pipeline_run(run: PipelineRunRecord, pipelinerun_json: dict | None = None) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO pipeline_runs
                   (id, pipeline_type_id, completion_time, status,
                    package_name, package_version, target_os,
                    event_type, git_org, git_repo, source_url,
                    pipeline_url, pipelinerun_json)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (id) DO NOTHING""",
                (
                    run.id,
                    run.pipeline_type_id,
                    run.completion_time,
                    run.status.value,
                    run.package_name,
                    run.package_version,
                    run.target_os,
                    run.event_type,
                    run.git_org,
                    run.git_repo,
                    run.source_url,
                    run.pipeline_url,
                    json.dumps(pipelinerun_json) if pipelinerun_json else None,
                ),
            )


def get_analyzed_pipeline_run_ids(pipeline_type_id: str) -> set[str]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT pipeline_run_id FROM analyses
                   WHERE status = 'completed'
                   AND pipeline_run_id IN (
                       SELECT id FROM pipeline_runs WHERE pipeline_type_id = %s
                   )""",
                (pipeline_type_id,),
            )
            return {row[0] for row in cur.fetchall()}


# ============================================================================
# Analyses
# ============================================================================


def insert_analysis(
    pipeline_run_id: str,
    result: AnalysisResult,
    thinking: str | None = None,
    version: int = 1,
) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO analyses
                   (pipeline_run_id, root_cause, category, confidence,
                    alternative_root_cause, alternative_confidence, ambiguity_note,
                    failed_task, failed_step, package_name, error_message,
                    evidence, details, suggested_action, remediation, thinking,
                    analysis_version, status, taxonomy_matched)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                           %s, %s, %s, %s, %s, %s, 'completed', %s)
                   RETURNING id""",
                (
                    pipeline_run_id,
                    result.root_cause,
                    result.category,
                    result.confidence,
                    result.alternative_root_cause,
                    result.alternative_confidence,
                    result.ambiguity_note,
                    result.failed_task,
                    result.failed_step,
                    result.package_name,
                    result.error_message,
                    result.evidence,
                    result.details,
                    result.suggested_action,
                    result.remediation,
                    thinking,
                    version,
                    result.taxonomy_matched,
                ),
            )
            return cur.fetchone()[0]


def get_latest_analysis_version(pipeline_run_id: str) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COALESCE(MAX(analysis_version), 0)
                   FROM analyses WHERE pipeline_run_id = %s""",
                (pipeline_run_id,),
            )
            return cur.fetchone()[0]


def check_taxonomy_match(root_cause: str, pipeline_type_id: str) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT 1 FROM taxonomy_rules
                   WHERE pipeline_type_id = %s AND root_cause = %s""",
                (pipeline_type_id, root_cause),
            )
            return cur.fetchone() is not None


def get_novel_analyses(pipeline_type_id: str, days: int = 90) -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT DISTINCT ON (a.pipeline_run_id)
                       a.id, a.pipeline_run_id, a.root_cause, a.category,
                       a.error_message, a.evidence, a.details,
                       a.suggested_action, a.remediation,
                       a.failed_task, a.failed_step
                   FROM analyses a
                   JOIN pipeline_runs pr ON a.pipeline_run_id = pr.id
                   WHERE pr.pipeline_type_id = %s
                     AND a.taxonomy_matched = FALSE
                     AND a.status = 'completed'
                     AND pr.completion_time > NOW() - INTERVAL '%s days'
                   ORDER BY a.pipeline_run_id, a.analysis_version DESC""",
                (pipeline_type_id, days),
            )
            return [dict(row) for row in cur.fetchall()]


def mark_analyses_taxonomy_matched(analysis_ids: list[int]) -> int:
    if not analysis_ids:
        return 0
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE analyses SET taxonomy_matched = TRUE WHERE id = ANY(%s)",
                (analysis_ids,),
            )
            return cur.rowcount


def get_unmatched_analyses_by_root_cause(
    root_cause: str, pipeline_type_id: str
) -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT DISTINCT ON (a.pipeline_run_id)
                       a.pipeline_run_id, pr.pipeline_type_id
                   FROM analyses a
                   JOIN pipeline_runs pr ON pr.id = a.pipeline_run_id
                   WHERE a.root_cause = %s
                     AND pr.pipeline_type_id = %s
                     AND a.status = 'completed'
                     AND (a.taxonomy_matched = FALSE OR a.taxonomy_matched IS NULL)
                   ORDER BY a.pipeline_run_id, a.analysis_version DESC""",
                (root_cause, pipeline_type_id),
            )
            return [dict(row) for row in cur.fetchall()]


def relabel_analyses(old_root_cause: str, new_root_cause: str, pipeline_type_id: str) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE analyses a SET root_cause = %s
                   FROM pipeline_runs pr
                   WHERE a.pipeline_run_id = pr.id
                     AND pr.pipeline_type_id = %s
                     AND a.root_cause = %s""",
                (new_root_cause, pipeline_type_id, old_root_cause),
            )
            return cur.rowcount


# ============================================================================
# Investigation Board
# ============================================================================


def post_to_board(pipeline_run_id: str, entry: BoardEntry) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO investigation_board
                   (pipeline_run_id, agent_type, findings, evidence,
                    classification_suggestion, confidence, flags, thinking)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (
                    pipeline_run_id,
                    entry.agent_type,
                    entry.findings,
                    entry.evidence,
                    entry.classification_suggestion,
                    entry.confidence,
                    entry.flags,
                    entry.thinking,
                ),
            )
            return cur.fetchone()[0]


def get_board_entries(pipeline_run_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM investigation_board
                   WHERE pipeline_run_id = %s ORDER BY created_at""",
                (pipeline_run_id,),
            )
            return [dict(row) for row in cur.fetchall()]


def clear_board(pipeline_run_id: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM investigation_board WHERE pipeline_run_id = %s",
                (pipeline_run_id,),
            )


# ============================================================================
# Artifacts
# ============================================================================


def insert_artifact(
    pipeline_run_id: str,
    artifact_type: ArtifactType,
    filename: str,
    content: str,
    size_bytes: int | None = None,
) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO artifacts
                   (pipeline_run_id, artifact_type, filename, content, size_bytes)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (pipeline_run_id, artifact_type) DO NOTHING
                   RETURNING id""",
                (pipeline_run_id, artifact_type.value, filename, content, size_bytes),
            )
            row = cur.fetchone()
            return row[0] if row else -1


def get_artifact(pipeline_run_id: str, artifact_type: ArtifactType) -> str | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT content FROM artifacts
                   WHERE pipeline_run_id = %s AND artifact_type = %s""",
                (pipeline_run_id, artifact_type.value),
            )
            row = cur.fetchone()
            return row[0] if row else None


# ============================================================================
# Taxonomy Rules
# ============================================================================


def get_taxonomy_rules(pipeline_type_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM taxonomy_rules
                   WHERE pipeline_type_id = %s ORDER BY priority_order""",
                (pipeline_type_id,),
            )
            return [dict(row) for row in cur.fetchall()]


def insert_taxonomy_rule(
    pipeline_type_id: str,
    root_cause: str,
    category: str,
    error_signature: str,
    priority_order: int,
    priority_rule: str | None = None,
    investigation_recipe: str | None = None,
    origin: str = "agent_proposed",
) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO taxonomy_rules
                   (pipeline_type_id, root_cause, category, error_signature,
                    priority_order, priority_rule, investigation_recipe, origin)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (pipeline_type_id, root_cause) DO NOTHING
                   RETURNING id""",
                (pipeline_type_id, root_cause, category, error_signature,
                 priority_order, priority_rule, investigation_recipe, origin),
            )
            row = cur.fetchone()
            return row[0] if row else -1


def update_taxonomy_rule(
    rule_id: int,
    root_cause: str | None = None,
    category: str | None = None,
    error_signature: str | None = None,
    priority_rule: str | None = None,
    investigation_recipe: str | None = None,
) -> bool:
    updates = []
    params: list[Any] = []
    if root_cause is not None:
        updates.append("root_cause = %s")
        params.append(root_cause)
    if category is not None:
        updates.append("category = %s")
        params.append(category)
    if error_signature is not None:
        updates.append("error_signature = %s")
        params.append(error_signature)
    if priority_rule is not None:
        updates.append("priority_rule = %s")
        params.append(priority_rule)
    if investigation_recipe is not None:
        updates.append("investigation_recipe = %s")
        params.append(investigation_recipe)
    if not updates:
        return False
    params.append(rule_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE taxonomy_rules SET {', '.join(updates)} WHERE id = %s",
                params,
            )
            return cur.rowcount > 0


def delete_taxonomy_rule(rule_id: int) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM taxonomy_rules WHERE id = %s", (rule_id,))
            return cur.rowcount > 0


# ============================================================================
# Rule Proposals
# ============================================================================


def insert_rule_proposal(proposal: RuleProposal) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO rule_proposals
                   (pipeline_type_id, pipeline_run_id, root_cause, category,
                    error_signature, priority_rule, investigation_recipe, reasoning)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (
                    proposal.pipeline_type_id,
                    proposal.pipeline_run_id,
                    proposal.root_cause,
                    proposal.category,
                    proposal.error_signature,
                    proposal.priority_rule,
                    proposal.investigation_recipe,
                    proposal.reasoning,
                ),
            )
            return cur.fetchone()[0]


def get_pending_proposals(pipeline_type_id: str | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if pipeline_type_id:
                cur.execute(
                    """SELECT * FROM rule_proposals
                       WHERE status = 'pending' AND pipeline_type_id = %s
                       ORDER BY created_at""",
                    (pipeline_type_id,),
                )
            else:
                cur.execute(
                    "SELECT * FROM rule_proposals WHERE status = 'pending' ORDER BY created_at"
                )
            return [dict(row) for row in cur.fetchall()]


def update_proposal_status(proposal_id: int, status: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE rule_proposals SET status = %s WHERE id = %s",
                (status, proposal_id),
            )


# ============================================================================
# Analysis Runs
# ============================================================================


def create_analysis_run(
    trigger: str, hours_back: int, pipeline_types: list[str]
) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO analysis_runs (trigger, hours_back, pipeline_types)
                   VALUES (%s, %s, %s) RETURNING id""",
                (trigger, hours_back, pipeline_types),
            )
            return cur.fetchone()[0]


def update_analysis_run(
    run_id: int,
    status: str | None = None,
    total_pipeline_runs: int | None = None,
    analyzed_count: int | None = None,
    total_cost_usd: float | None = None,
    error_message: str | None = None,
) -> None:
    updates = []
    params: list[Any] = []
    if status is not None:
        updates.append("status = %s")
        params.append(status)
        if status in ("completed", "failed"):
            updates.append("completed_at = NOW()")
    if total_pipeline_runs is not None:
        updates.append("total_pipeline_runs = %s")
        params.append(total_pipeline_runs)
    if analyzed_count is not None:
        updates.append("analyzed_count = %s")
        params.append(analyzed_count)
    if total_cost_usd is not None:
        updates.append("total_cost_usd = %s")
        params.append(total_cost_usd)
    if error_message is not None:
        updates.append("error_message = %s")
        params.append(error_message)
    if not updates:
        return
    params.append(run_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE analysis_runs SET {', '.join(updates)} WHERE id = %s",
                params,
            )


def get_analysis_run_total_cost(run_id: int) -> float:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) FROM cost_entries WHERE analysis_run_id = %s",
                (run_id,),
            )
            return float(cur.fetchone()[0])


# ============================================================================
# Conversation Logs
# ============================================================================


def insert_conversation_log(
    pipeline_run_id: str,
    analysis_version: int,
    s3_key: str,
    summary: str | None = None,
    agent_sequence: list[str] | None = None,
    total_tokens: int | None = None,
    total_cost_usd: float | None = None,
) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO conversation_logs
                   (pipeline_run_id, analysis_version, s3_key, summary,
                    agent_sequence, total_tokens, total_cost_usd)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (pipeline_run_id, analysis_version) DO UPDATE
                   SET s3_key = EXCLUDED.s3_key, summary = EXCLUDED.summary,
                       agent_sequence = EXCLUDED.agent_sequence,
                       total_tokens = EXCLUDED.total_tokens,
                       total_cost_usd = EXCLUDED.total_cost_usd
                   RETURNING id""",
                (
                    pipeline_run_id,
                    analysis_version,
                    s3_key,
                    summary,
                    agent_sequence,
                    total_tokens,
                    total_cost_usd,
                ),
            )
            return cur.fetchone()[0]


def get_conversation_log(pipeline_run_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM conversation_logs
                   WHERE pipeline_run_id = %s
                   ORDER BY analysis_version DESC LIMIT 1""",
                (pipeline_run_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


# ============================================================================
# Collect Requests (API → Collector queue)
# ============================================================================


def create_collect_request(
    pipeline_types: list[str] | None = None,
    hours_back: int = 24,
    requested_by: str = "api",
) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO collect_requests
                   (pipeline_types, hours_back, requested_by)
                   VALUES (%s, %s, %s) RETURNING id""",
                (pipeline_types, hours_back, requested_by),
            )
            return cur.fetchone()[0]


def get_pending_collect_request() -> dict[str, Any] | None:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """UPDATE collect_requests
                   SET status = 'in_progress'
                   WHERE id = (
                       SELECT id FROM collect_requests
                       WHERE status = 'pending'
                       ORDER BY created_at ASC
                       LIMIT 1
                       FOR UPDATE SKIP LOCKED
                   )
                   RETURNING *""",
            )
            row = cur.fetchone()
            return dict(row) if row else None


def complete_collect_request(request_id: int, analysis_run_id: int | None = None) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE collect_requests
                   SET status = 'completed', completed_at = NOW(), analysis_run_id = %s
                   WHERE id = %s""",
                (analysis_run_id, request_id),
            )


def fail_collect_request(request_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE collect_requests
                   SET status = 'failed', completed_at = NOW()
                   WHERE id = %s""",
                (request_id,),
            )


# ============================================================================
# Re-analysis Queue
# ============================================================================


def queue_reanalysis(
    pipeline_run_id: str, pipeline_type_id: str, reason: str, triggered_by: str = "auto"
) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO re_analysis_queue
                   (pipeline_run_id, pipeline_type_id, reason, triggered_by)
                   VALUES (%s, %s, %s, %s)""",
                (pipeline_run_id, pipeline_type_id, reason, triggered_by),
            )


def get_pending_reanalysis() -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM re_analysis_queue
                   WHERE status = 'pending' ORDER BY created_at"""
            )
            return [dict(row) for row in cur.fetchall()]


def update_reanalysis_status(queue_id: int, status: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE re_analysis_queue SET status = %s WHERE id = %s",
                (status, queue_id),
            )


# ============================================================================
# Cost Tracking
# ============================================================================


def insert_cost_entry(entry: CostEntry) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO cost_entries
                   (analysis_run_id, pipeline_run_id, invocation_type,
                    chat_session_id, cost_usd, input_tokens, output_tokens,
                    cache_read_tokens, cache_creation_tokens, duration_ms, model)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    entry.analysis_run_id,
                    entry.pipeline_run_id,
                    entry.invocation_type.value,
                    entry.chat_session_id,
                    entry.cost_usd,
                    entry.input_tokens,
                    entry.output_tokens,
                    entry.cache_read_tokens,
                    entry.cache_creation_tokens,
                    entry.duration_ms,
                    entry.model,
                ),
            )


def get_cost_summary(days: int = 30) -> dict:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT invocation_type, COUNT(*) as calls,
                          ROUND(SUM(cost_usd)::numeric, 6) as total_cost,
                          SUM(input_tokens) as input_tokens,
                          SUM(output_tokens) as output_tokens,
                          SUM(cache_read_tokens) as cache_read_tokens,
                          ROUND(AVG(duration_ms)::numeric, 0) as avg_duration_ms
                   FROM cost_entries
                   WHERE created_at >= NOW() - INTERVAL '%s days'
                   GROUP BY invocation_type
                   ORDER BY total_cost DESC""",
                (days,),
            )
            by_type = [dict(r) for r in cur.fetchall()]

            cur.execute(
                """SELECT DATE(created_at) as day, invocation_type,
                          COUNT(*) as calls,
                          ROUND(SUM(cost_usd)::numeric, 6) as cost
                   FROM cost_entries
                   WHERE created_at >= NOW() - INTERVAL '%s days'
                   GROUP BY day, invocation_type
                   ORDER BY day""",
                (days,),
            )
            daily = [dict(r) for r in cur.fetchall()]

            cur.execute(
                """SELECT id, invocation_type, model, cost_usd,
                          input_tokens, output_tokens,
                          cache_read_tokens, cache_creation_tokens,
                          duration_ms, pipeline_run_id, chat_session_id,
                          created_at
                   FROM cost_entries
                   WHERE created_at >= NOW() - INTERVAL '%s days'
                   ORDER BY created_at DESC
                   LIMIT 200""",
                (days,),
            )
            recent = [dict(r) for r in cur.fetchall()]

    return {"by_type": by_type, "daily": daily, "recent": recent}


# ============================================================================
# Historical Analysis Queries
# ============================================================================


def get_recent_analyses(
    pipeline_type_id: str, root_cause: str, days: int | None = None, limit: int = 10
) -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            time_filter = ""
            params: tuple = (pipeline_type_id, root_cause)
            if days is not None:
                time_filter = "AND pr.completion_time > NOW() - INTERVAL '%s days'"
                params = (pipeline_type_id, root_cause, days)
            cur.execute(
                f"""SELECT DISTINCT ON (a.pipeline_run_id)
                       a.pipeline_run_id, a.root_cause, a.category, a.confidence,
                       a.error_message, a.evidence, a.details, a.analysis_version,
                       pr.completion_time, pr.package_name
                   FROM analyses a
                   JOIN pipeline_runs pr ON a.pipeline_run_id = pr.id
                   WHERE pr.pipeline_type_id = %s
                     AND a.root_cause = %s
                     AND a.status = 'completed'
                     {time_filter}
                   ORDER BY a.pipeline_run_id, a.analysis_version DESC""",
                params,
            )
            rows = [dict(row) for row in cur.fetchall()]
            rows.sort(key=lambda r: r.get("completion_time") or "", reverse=True)
            return rows[:limit]


def get_recent_unknowns(
    pipeline_type_id: str, days: int = 30, limit: int = 10
) -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT DISTINCT ON (a.pipeline_run_id)
                       a.pipeline_run_id, a.root_cause, a.category, a.confidence,
                       a.error_message, a.evidence, a.details, a.analysis_version,
                       pr.completion_time, pr.package_name
                   FROM analyses a
                   JOIN pipeline_runs pr ON a.pipeline_run_id = pr.id
                   WHERE pr.pipeline_type_id = %s
                     AND a.root_cause = 'unknown'
                     AND a.status = 'completed'
                     AND pr.completion_time > NOW() - INTERVAL '%s days'
                   ORDER BY a.pipeline_run_id, a.analysis_version DESC""",
                (pipeline_type_id, days),
            )
            rows = [dict(row) for row in cur.fetchall()]
            rows.sort(key=lambda r: r.get("completion_time") or "", reverse=True)
            return rows[:limit]


# ============================================================================
# Pipeline Types
# ============================================================================


def get_pipeline_types() -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM pipeline_types ORDER BY id")
            return [dict(row) for row in cur.fetchall()]


# ============================================================================
# API Query Helpers
# ============================================================================


def get_pipeline_runs(
    pipeline_type_id: str | None = None,
    status: str | None = None,
    package_name: str | None = None,
    days: int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    root_cause: str | None = None,
    root_cause_search: str | None = None,
    has_root_cause: bool | None = None,
    taxonomy_matched: bool | None = None,
    name_search: str | None = None,
    page: int = 1,
    per_page: int = 200,
) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
    base_conditions: list[str] = []
    base_params: list[Any] = []

    if pipeline_type_id:
        base_conditions.append("pr.pipeline_type_id = %s")
        base_params.append(pipeline_type_id)
    if package_name:
        base_conditions.append("pr.package_name = %s")
        base_params.append(package_name)
    if days:
        base_conditions.append("pr.completion_time > NOW() - INTERVAL '%s days'")
        base_params.append(days)
    if from_date:
        base_conditions.append("pr.completion_time >= %s")
        base_params.append(from_date)
    if to_date:
        base_conditions.append("pr.completion_time <= %s")
        base_params.append(to_date)
    if root_cause:
        base_conditions.append("a.root_cause = %s")
        base_params.append(root_cause)
    if root_cause_search:
        base_conditions.append("a.root_cause ILIKE %s")
        base_params.append(f"%{root_cause_search}%")
    if has_root_cause is not None:
        if has_root_cause:
            base_conditions.append("a.root_cause IS NOT NULL")
        else:
            base_conditions.append("a.root_cause IS NULL")
    if taxonomy_matched is not None:
        base_conditions.append("a.taxonomy_matched = %s")
        base_params.append(taxonomy_matched)
    if name_search:
        base_conditions.append("pr.id ILIKE %s")
        base_params.append(f"%{name_search}%")

    status_conditions = list(base_conditions)
    status_params = list(base_params)
    if status:
        status_conditions.append("pr.status = %s")
        status_params.append(status)

    base_where = f"WHERE {' AND '.join(base_conditions)}" if base_conditions else ""
    full_where = f"WHERE {' AND '.join(status_conditions)}" if status_conditions else ""

    lateral_join = """LEFT JOIN LATERAL (
                        SELECT * FROM analyses
                        WHERE pipeline_run_id = pr.id
                          AND status = 'completed'
                        ORDER BY analysis_version DESC LIMIT 1
                    ) a ON true"""

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""SELECT pr.status,
                           COUNT(DISTINCT pr.id) AS cnt,
                           COUNT(DISTINCT pr.id) FILTER (
                               WHERE pr.status = 'failed' AND a.root_cause IS NULL
                           ) AS unknown_cnt,
                           COUNT(DISTINCT pr.id) FILTER (
                               WHERE pr.status = 'failed' AND a.taxonomy_matched = false
                           ) AS novel_cnt
                    FROM pipeline_runs pr
                    {lateral_join}
                    {base_where}
                    GROUP BY pr.status""",
                base_params,
            )
            counts: dict[str, int] = {
                "all": 0, "failed": 0, "succeeded": 0, "aborted": 0,
                "unknown": 0, "novel": 0,
            }
            for row in cur.fetchall():
                counts[row["status"]] = row["cnt"]
                counts["all"] += row["cnt"]
                if row["status"] == "failed":
                    counts["unknown"] = row["unknown_cnt"]
                    counts["novel"] = row["novel_cnt"]

            cur.execute(
                f"""SELECT COUNT(DISTINCT pr.id)
                    FROM pipeline_runs pr
                    {lateral_join}
                    {full_where}""",
                status_params,
            )
            total = cur.fetchone()["count"]

            offset = (page - 1) * per_page
            cur.execute(
                f"""SELECT pr.id, pr.pipeline_type_id, pr.completion_time,
                       pr.status, pr.package_name, pr.package_version,
                       pr.target_os, pr.event_type, pr.git_org, pr.git_repo,
                       pr.source_url, pr.pipeline_url,
                       a.root_cause, a.category, a.confidence,
                       a.alternative_root_cause, a.alternative_confidence,
                       a.ambiguity_note,
                       a.failed_task, a.failed_step, a.package_name AS analysis_package_name,
                       a.error_message, a.evidence, a.details,
                       a.suggested_action, a.remediation, a.analysis_version,
                       a.taxonomy_matched
                    FROM pipeline_runs pr
                    {lateral_join}
                    {full_where}
                    ORDER BY pr.completion_time DESC
                    LIMIT %s OFFSET %s""",
                [*status_params, per_page, offset],
            )
            rows = [dict(row) for row in cur.fetchall()]
            return rows, total, counts


def get_pipeline_run_detail(pipeline_run_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT pr.*,
                       a.root_cause, a.category, a.confidence,
                       a.alternative_root_cause, a.alternative_confidence,
                       a.ambiguity_note,
                       a.failed_task, a.failed_step,
                       a.package_name AS analysis_package_name,
                       a.error_message, a.evidence, a.details,
                       a.suggested_action, a.remediation, a.thinking,
                       a.analysis_version, a.taxonomy_matched
                    FROM pipeline_runs pr
                    LEFT JOIN LATERAL (
                        SELECT * FROM analyses
                        WHERE pipeline_run_id = pr.id
                          AND status = 'completed'
                        ORDER BY analysis_version DESC LIMIT 1
                    ) a ON true
                    WHERE pr.id = %s""",
                (pipeline_run_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_analysis_history(pipeline_run_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM analyses
                   WHERE pipeline_run_id = %s
                   ORDER BY analysis_version DESC""",
                (pipeline_run_id,),
            )
            return [dict(row) for row in cur.fetchall()]


def get_stats(
    pipeline_type_id: str | None = None,
    days: int = 30,
) -> dict[str, Any]:
    conditions = ["pr.completion_time > NOW() - INTERVAL '%s days'"]
    params: list[Any] = [days]

    if pipeline_type_id:
        conditions.append("pr.pipeline_type_id = %s")
        params.append(pipeline_type_id)

    where = f"WHERE {' AND '.join(conditions)}"

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""SELECT
                        COUNT(*) AS total,
                        COUNT(*) FILTER (WHERE pr.status = 'succeeded') AS succeeded,
                        COUNT(*) FILTER (WHERE pr.status = 'failed') AS failed,
                        COUNT(*) FILTER (WHERE pr.status = 'aborted') AS aborted
                    FROM pipeline_runs pr {where}""",
                params,
            )
            counts = dict(cur.fetchone())

            cur.execute(
                f"""SELECT
                        DATE(pr.completion_time) AS date,
                        COUNT(*) FILTER (WHERE pr.status = 'succeeded') AS succeeded,
                        COUNT(*) FILTER (WHERE pr.status = 'failed') AS failed,
                        COUNT(*) FILTER (WHERE pr.status = 'aborted') AS aborted
                    FROM pipeline_runs pr {where}
                    GROUP BY DATE(pr.completion_time)
                    ORDER BY date""",
                params,
            )
            daily = [dict(row) for row in cur.fetchall()]

            rc_conditions = conditions + ["pr.status = 'failed'"]
            rc_where = f"WHERE {' AND '.join(rc_conditions)}"
            cur.execute(
                f"""SELECT
                        COALESCE(a.root_cause, 'unanalyzed') AS root_cause,
                        COALESCE(a.category, 'unknown') AS category,
                        COUNT(*) AS count
                    FROM pipeline_runs pr
                    LEFT JOIN LATERAL (
                        SELECT root_cause, category FROM analyses
                        WHERE pipeline_run_id = pr.id
                          AND status = 'completed'
                        ORDER BY analysis_version DESC LIMIT 1
                    ) a ON true
                    {rc_where}
                    GROUP BY a.root_cause, a.category
                    ORDER BY count DESC""",
                params,
            )
            root_causes = [dict(row) for row in cur.fetchall()]

            return {
                **counts,
                "pass_rate": round(
                    counts["succeeded"] / counts["total"] * 100, 1
                )
                if counts["total"] > 0
                else 0,
                "daily": daily,
                "root_causes": root_causes,
            }


def get_analysis_runs(limit: int = 20) -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM analysis_runs
                   ORDER BY started_at DESC LIMIT %s""",
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]


def get_analysis_run_detail(run_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM analysis_runs WHERE id = %s", (run_id,))
            row = cur.fetchone()
            if not row:
                return None
            result = dict(row)

            cur.execute(
                """SELECT invocation_type,
                       COUNT(*) AS call_count,
                       SUM(cost_usd) AS total_cost,
                       SUM(input_tokens) AS total_input_tokens,
                       SUM(output_tokens) AS total_output_tokens
                   FROM cost_entries
                   WHERE analysis_run_id = %s
                   GROUP BY invocation_type""",
                (run_id,),
            )
            result["cost_breakdown"] = [dict(r) for r in cur.fetchall()]

            cur.execute(
                """SELECT DISTINCT pr.id, pr.pipeline_type_id, pr.status,
                       pr.package_name, pr.event_type,
                       pr.git_org, pr.git_repo,
                       a.root_cause, a.category, a.confidence
                   FROM cost_entries ce
                   JOIN pipeline_runs pr ON pr.id = ce.pipeline_run_id
                   LEFT JOIN analyses a ON a.pipeline_run_id = pr.id
                       AND a.analysis_version = (
                           SELECT MAX(a2.analysis_version)
                           FROM analyses a2
                           WHERE a2.pipeline_run_id = pr.id
                       )
                   WHERE ce.analysis_run_id = %s
                     AND ce.pipeline_run_id IS NOT NULL
                   ORDER BY pr.pipeline_type_id, pr.id""",
                (run_id,),
            )
            result["pipeline_runs"] = [dict(r) for r in cur.fetchall()]

            cur.execute(
                """SELECT DISTINCT rp.id, rp.pipeline_type_id, rp.root_cause,
                       rp.category, rp.status, rp.reasoning
                   FROM rule_proposals rp
                   JOIN cost_entries ce ON ce.pipeline_run_id = rp.pipeline_run_id
                   WHERE ce.analysis_run_id = %s
                   ORDER BY rp.id""",
                (run_id,),
            )
            result["taxonomy_changes"] = [dict(r) for r in cur.fetchall()]

            return result


# ============================================================================
# Chat Sessions & Messages
# ============================================================================


def create_chat_session(
    title: str | None = None,
    context_pipeline_run_id: str | None = None,
) -> str:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO chat_sessions (title, context_pipeline_run_id)
                   VALUES (%s, %s) RETURNING id""",
                (title, context_pipeline_run_id),
            )
            return str(cur.fetchone()[0])


def update_chat_session_title(session_id: str, title: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE chat_sessions SET title = %s WHERE id = %s",
                (title, session_id),
            )


def get_chat_sessions(limit: int = 20) -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM chat_sessions
                   ORDER BY updated_at DESC LIMIT %s""",
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]


def get_chat_messages(session_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM chat_messages
                   WHERE session_id = %s ORDER BY id ASC""",
                (session_id,),
            )
            return [dict(row) for row in cur.fetchall()]


def insert_chat_message(
    session_id: str,
    role: str,
    content: str,
    tool_calls: dict | list | None = None,
    cost_usd: float | None = None,
    tokens_used: int | None = None,
) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO chat_messages
                   (session_id, role, content, tool_calls, cost_usd, tokens_used)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (
                    session_id,
                    role,
                    content,
                    json.dumps(tool_calls) if tool_calls else None,
                    cost_usd,
                    tokens_used,
                ),
            )
            msg_id = cur.fetchone()[0]
            cur.execute(
                "UPDATE chat_sessions SET updated_at = NOW() WHERE id = %s",
                (session_id,),
            )
            return msg_id


# ============================================================================
# Health Check
# ============================================================================


def check_db_health() -> dict[str, Any]:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.execute(
                    """SELECT
                        (SELECT COUNT(*) FROM pipeline_runs) AS total_runs,
                        (SELECT COUNT(*) FROM pipeline_runs
                         WHERE status = 'failed') AS total_failed,
                        (SELECT COUNT(*) FROM analyses) AS total_analyses,
                        (SELECT MAX(started_at) FROM analysis_runs) AS last_run,
                        (SELECT status FROM analysis_runs
                         ORDER BY started_at DESC LIMIT 1) AS last_run_status,
                        (SELECT COUNT(*) FROM re_analysis_queue
                         WHERE status = 'pending') AS pending_reanalysis,
                        (SELECT COUNT(*) FROM rule_proposals
                         WHERE status = 'pending') AS pending_proposals,
                        (SELECT COUNT(*) FROM collect_requests
                         WHERE status = 'pending') AS pending_collect,
                        (SELECT pg_database_size(current_database())) AS db_size_bytes"""
                )
                row = cur.fetchone()
                return {
                    "status": "ok",
                    "total_runs": row[0],
                    "total_failed": row[1],
                    "total_analyses": row[2],
                    "last_analysis_run": str(row[3]) if row[3] else None,
                    "last_run_status": row[4],
                    "pending_reanalysis": row[5],
                    "pending_proposals": row[6],
                    "pending_collect": row[7],
                    "db_size_mb": round(row[8] / 1048576, 1) if row[8] else None,
                }
    except Exception as e:
        return {"status": "error", "error": str(e)}
