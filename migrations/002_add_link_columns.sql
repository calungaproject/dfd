-- Add source_url (GitHub PR/commit link) and pipeline_url (Konflux UI link)
-- to pipeline_runs. Populated by the collector from PipelineRun annotations.
-- Run scripts/backfill_run_metadata.py after this migration to fill existing rows.

ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS source_url TEXT;
ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS pipeline_url TEXT;
