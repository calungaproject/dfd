-- DFD Initial Schema — PostgreSQL 16 (no pgvector)

-- ============================================================================
-- Pipeline types tracked by the system
-- ============================================================================
CREATE TABLE pipeline_types (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    label_selector TEXT NOT NULL,
    namespace TEXT NOT NULL,
    description TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Example seed data — update namespace, label_selector, and description for your project
INSERT INTO pipeline_types (id, display_name, label_selector, namespace, description) VALUES
    ('build', 'Build', 'pipelines.appstudio.openshift.io/type=build', 'example-tenant', 'Source builds'),
    ('integration_test', 'Integration Test', 'pipelines.appstudio.openshift.io/type=test,tekton.dev/pipeline=integration-test', 'example-tenant', 'Integration tests'),
    ('enterprise_contract', 'Enterprise Contract', 'pipelines.appstudio.openshift.io/type=test,tekton.dev/pipeline=enterprise-contract', 'example-tenant', 'EC validation and signing'),
    ('release', 'Release', 'pipelines.appstudio.openshift.io/type=managed,release.appstudio.openshift.io/namespace=example-tenant', 'example-releng-tenant', 'Release pipeline');

-- ============================================================================
-- Pipeline runs (succeeded, failed, aborted)
-- ============================================================================
CREATE TABLE pipeline_runs (
    id TEXT PRIMARY KEY,
    pipeline_type_id TEXT NOT NULL REFERENCES pipeline_types(id),
    completion_time TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('succeeded', 'failed', 'aborted')),
    package_name TEXT,
    package_version TEXT,
    target_os TEXT,
    event_type TEXT,
    git_org TEXT,
    git_repo TEXT,
    pipelinerun_json JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_pr_pipeline_type ON pipeline_runs(pipeline_type_id);
CREATE INDEX idx_pr_completion ON pipeline_runs(completion_time DESC);
CREATE INDEX idx_pr_status ON pipeline_runs(status);
CREATE INDEX idx_pr_package ON pipeline_runs(package_name);

-- ============================================================================
-- Analysis results for failed runs
-- ============================================================================
CREATE TABLE analyses (
    id SERIAL PRIMARY KEY,
    pipeline_run_id TEXT NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    root_cause TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('build', 'infra', 'unknown')),
    confidence INT NOT NULL DEFAULT 100 CHECK (confidence BETWEEN 0 AND 100),
    alternative_root_cause TEXT,
    alternative_confidence INT CHECK (alternative_confidence IS NULL
        OR alternative_confidence BETWEEN 0 AND 100),
    ambiguity_note TEXT,
    failed_task TEXT,
    failed_step TEXT,
    package_name TEXT,
    error_message TEXT,
    evidence TEXT,
    details TEXT,
    suggested_action TEXT,
    remediation TEXT,
    thinking TEXT,
    analysis_version INT NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed', 'failed')),
    taxonomy_matched BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(pipeline_run_id, analysis_version)
);

-- ============================================================================
-- Investigation board (multi-agent communication workspace)
-- ============================================================================
CREATE TABLE investigation_board (
    id SERIAL PRIMARY KEY,
    pipeline_run_id TEXT NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    agent_type TEXT NOT NULL,
    findings TEXT NOT NULL,
    evidence TEXT,
    classification_suggestion TEXT,
    confidence TEXT CHECK (confidence IS NULL OR confidence IN ('high', 'medium', 'low')),
    flags TEXT,
    thinking TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_board_pr ON investigation_board(pipeline_run_id);

-- ============================================================================
-- Key artifacts stored in DB (logs, TaskRun JSON, metadata)
-- ============================================================================
CREATE TABLE artifacts (
    id SERIAL PRIMARY KEY,
    pipeline_run_id TEXT NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL
        CHECK (artifact_type IN ('failed_step_log', 'taskruns_json', 'metadata_json')),
    filename TEXT NOT NULL,
    content TEXT NOT NULL,
    size_bytes INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(pipeline_run_id, artifact_type)
);
CREATE INDEX idx_artifacts_pr ON artifacts(pipeline_run_id);

-- ============================================================================
-- Taxonomy rules (per pipeline_type)
-- ============================================================================
CREATE TABLE taxonomy_rules (
    id SERIAL PRIMARY KEY,
    pipeline_type_id TEXT NOT NULL REFERENCES pipeline_types(id),
    root_cause TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('build', 'infra', 'unknown')),
    error_signature TEXT NOT NULL,
    priority_order INT NOT NULL,
    priority_rule TEXT,
    investigation_recipe TEXT,
    origin TEXT NOT NULL DEFAULT 'manual'
        CHECK (origin IN ('manual', 'agent_proposed', 'agent_proposed_reviewed',
                          'auto_consolidation')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(pipeline_type_id, root_cause)
);

-- ============================================================================
-- Rule proposals from agents
-- ============================================================================
CREATE TABLE rule_proposals (
    id SERIAL PRIMARY KEY,
    pipeline_type_id TEXT NOT NULL REFERENCES pipeline_types(id),
    pipeline_run_id TEXT REFERENCES pipeline_runs(id),
    root_cause TEXT NOT NULL,
    category TEXT NOT NULL,
    error_signature TEXT NOT NULL,
    priority_rule TEXT NOT NULL,
    investigation_recipe TEXT,
    reasoning TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'rejected', 'duplicate')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Analysis run batches
-- ============================================================================
CREATE TABLE analysis_runs (
    id SERIAL PRIMARY KEY,
    trigger TEXT NOT NULL CHECK (trigger IN ('scheduled', 'manual', 'api')),
    hours_back INT NOT NULL DEFAULT 24,
    pipeline_types TEXT[] NOT NULL,
    status TEXT NOT NULL DEFAULT 'collecting'
        CHECK (status IN ('collecting', 'analyzing', 'completed', 'failed')),
    total_pipeline_runs INT DEFAULT 0,
    analyzed_count INT DEFAULT 0,
    total_cost_usd NUMERIC(10,4) DEFAULT 0,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error_message TEXT
);

-- ============================================================================
-- Conversation logs (summary in DB, full JSON in S3)
-- ============================================================================
CREATE TABLE conversation_logs (
    id SERIAL PRIMARY KEY,
    pipeline_run_id TEXT NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    analysis_version INT NOT NULL,
    s3_key TEXT NOT NULL,
    summary TEXT,
    agent_sequence TEXT[],
    total_tokens INT,
    total_cost_usd NUMERIC(10,6),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(pipeline_run_id, analysis_version)
);

-- ============================================================================
-- Cost tracking per LLM invocation
-- ============================================================================
CREATE TABLE cost_entries (
    id SERIAL PRIMARY KEY,
    analysis_run_id INT REFERENCES analysis_runs(id),
    pipeline_run_id TEXT REFERENCES pipeline_runs(id),
    invocation_type TEXT NOT NULL
        CHECK (invocation_type IN ('analysis', 'reanalysis', 'consolidation', 'chat')),
    chat_session_id UUID,
    cost_usd NUMERIC(10,6) NOT NULL,
    input_tokens INT,
    output_tokens INT,
    cache_read_tokens INT,
    cache_creation_tokens INT,
    duration_ms INT,
    model TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Re-analysis queue
-- ============================================================================
CREATE TABLE re_analysis_queue (
    id SERIAL PRIMARY KEY,
    pipeline_run_id TEXT NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    pipeline_type_id TEXT NOT NULL REFERENCES pipeline_types(id),
    reason TEXT NOT NULL,
    triggered_by TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed', 'skipped')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_reanalysis_status ON re_analysis_queue(status);

-- ============================================================================
-- Chat sessions & messages
-- ============================================================================
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT,
    context_pipeline_run_id TEXT REFERENCES pipeline_runs(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    tool_calls JSONB,
    cost_usd NUMERIC(10,6),
    tokens_used INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_chat_messages_session ON chat_messages(session_id);

-- ============================================================================
-- Collect request queue (API -> Collector communication)
-- ============================================================================
CREATE TABLE collect_requests (
    id SERIAL PRIMARY KEY,
    pipeline_types TEXT[],
    hours_back INT DEFAULT 24,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed', 'failed')),
    requested_by TEXT DEFAULT 'api',
    analysis_run_id INT REFERENCES analysis_runs(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX idx_collect_status ON collect_requests(status);

-- ============================================================================
-- Schema migration tracking
-- ============================================================================
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT NOW()
);
