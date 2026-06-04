"""Pydantic models for DFD shared data types."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# -- Enums --


class RunStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABORTED = "aborted"


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class RuleCategory(str, Enum):
    BUILD = "build"
    INFRA = "infra"
    UNKNOWN = "unknown"


class RuleOrigin(str, Enum):
    MANUAL = "manual"
    AGENT_PROPOSED = "agent_proposed"
    AGENT_PROPOSED_REVIEWED = "agent_proposed_reviewed"
    AUTO_CONSOLIDATION = "auto_consolidation"


class ProposalStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"


class RunTrigger(str, Enum):
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    API = "api"


class ArtifactType(str, Enum):
    FAILED_STEP_LOG = "failed_step_log"
    TASKRUNS_JSON = "taskruns_json"
    METADATA_JSON = "metadata_json"


class InvocationType(str, Enum):
    ANALYSIS = "analysis"
    REANALYSIS = "reanalysis"
    CONSOLIDATION = "consolidation"
    CHAT = "chat"


# -- Pipeline Run Models --


class PipelineRunRecord(BaseModel):
    """A pipeline run as stored in the DB."""

    id: str
    pipeline_type_id: str
    completion_time: datetime
    status: RunStatus
    namespace: str | None = None
    package_name: str | None = None
    package_version: str | None = None
    target_os: str | None = None
    event_type: str | None = None
    git_org: str | None = None
    git_repo: str | None = None
    source_url: str | None = None
    pipeline_url: str | None = None


class PipelineRunMetadata(BaseModel):
    """Metadata extracted from KubeArchive for a failed pipeline run."""

    pipelinerun: str
    pipeline_type: str
    package_name: str | None = None
    package_version: str | None = None
    failed_task: str | None = None
    failed_step: str | None = None
    pod_name: str | None = None
    completion_time: str | None = None
    condition_message: str | None = None


# -- Analysis Models --


class AnalysisResult(BaseModel):
    """Structured analysis output from the multi-agent pipeline."""

    root_cause: str
    category: str
    confidence: int = Field(default=100, ge=0, le=100)
    alternative_root_cause: str | None = None
    alternative_confidence: int | None = Field(default=None, ge=0, le=100)
    ambiguity_note: str | None = None
    failed_task: str | None = None
    failed_step: str | None = None
    package_name: str | None = None
    error_message: str | None = None
    evidence: str | None = None
    details: str | None = None
    suggested_action: str | None = None
    remediation: str | None = None
    taxonomy_matched: bool = True


class BoardEntry(BaseModel):
    """An entry on the investigation board from one agent."""

    agent_type: str
    findings: str
    evidence: str | None = None
    classification_suggestion: str | None = None
    confidence: str | None = None
    flags: str | None = None
    thinking: str | None = None


# -- Taxonomy Models --


class TaxonomyRule(BaseModel):
    """A taxonomy classification rule."""

    id: int | None = None
    pipeline_type_id: str
    root_cause: str
    category: RuleCategory
    error_signature: str
    priority_order: int
    priority_rule: str | None = None
    investigation_recipe: str | None = None
    origin: RuleOrigin = RuleOrigin.MANUAL


class RuleProposal(BaseModel):
    """A rule proposal from an analysis agent."""

    pipeline_type_id: str
    pipeline_run_id: str | None = None
    root_cause: str
    category: str
    error_signature: str
    priority_rule: str
    investigation_recipe: str | None = None
    reasoning: str | None = None


# -- Artifact Models --


class ArtifactRecord(BaseModel):
    """A key artifact stored in the DB."""

    pipeline_run_id: str
    artifact_type: ArtifactType
    filename: str
    content: str
    size_bytes: int | None = None


# -- Cost Tracking --


class CostEntry(BaseModel):
    """Cost data for a single LLM invocation."""

    analysis_run_id: int | None = None
    pipeline_run_id: str | None = None
    invocation_type: InvocationType
    chat_session_id: str | None = None
    cost_usd: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_creation_tokens: int | None = None
    duration_ms: int | None = None
    model: str | None = None
