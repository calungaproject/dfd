"""DFD configuration — loads environment variables and pipeline type definitions."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PipelineTypeConfig:
    """Static configuration for a monitored pipeline type."""

    id: str
    display_name: str
    label_selector: str
    namespace: str
    description: str = ""


def load_pipeline_types() -> dict[str, PipelineTypeConfig]:
    """Load pipeline type definitions from the database.

    Must be called after db.init_pool().
    """
    from dfd.common import db

    rows = db.get_pipeline_types()
    return {
        row["id"]: PipelineTypeConfig(
            id=row["id"],
            display_name=row["display_name"],
            label_selector=row["label_selector"],
            namespace=row["namespace"],
            description=row.get("description", ""),
        )
        for row in rows
        if row.get("enabled", True)
    }


@dataclass
class Settings:
    """Runtime settings loaded from environment variables."""

    # Database
    database_url: str = field(default_factory=lambda: os.environ["DATABASE_URL"])

    # KubeArchive
    kubearchive_url: str = field(
        default_factory=lambda: os.environ.get("KUBEARCHIVE_URL", "")
    )
    kubearchive_token: str = field(
        default_factory=lambda: os.environ.get("KUBEARCHIVE_TOKEN", "")
    )
    kubearchive_verify_tls: bool = field(
        default_factory=lambda: os.environ.get("KUBEARCHIVE_VERIFY_TLS", "true").lower()
        not in ("false", "0", "no"),
    )

    # Vertex AI / Claude
    google_cloud_project: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    )
    google_cloud_region: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_CLOUD_REGION", "us-east5")
    )
    claude_model: str = field(
        default_factory=lambda: os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    )

    # S3
    s3_endpoint_url: str = field(
        default_factory=lambda: os.environ.get("S3_ENDPOINT_URL", "")
    )
    s3_bucket: str = field(
        default_factory=lambda: os.environ.get("S3_BUCKET", "dfd")
    )

    # Collector
    collect_interval_hours: int = field(
        default_factory=lambda: int(os.environ.get("COLLECT_INTERVAL_HOURS", "24"))
    )
    collect_hours_back: int = field(
        default_factory=lambda: int(os.environ.get("COLLECT_HOURS_BACK", "48"))
    )
    collect_poll_interval_seconds: int = field(
        default_factory=lambda: int(os.environ.get("COLLECT_POLL_INTERVAL_SECONDS", "30"))
    )

    # Analysis
    max_parallel_specialists: int = field(
        default_factory=lambda: int(os.environ.get("MAX_PARALLEL_SPECIALISTS", "5"))
    )
    thinking_budget_tokens: int = field(
        default_factory=lambda: int(os.environ.get("THINKING_BUDGET_TOKENS", "10000"))
    )

    # Pipeline types to process (comma-separated, default: all)
    enabled_pipeline_types: list[str] = field(
        default_factory=lambda: _parse_pipeline_types()
    )


def _parse_pipeline_types() -> list[str]:
    raw = os.environ.get("ENABLED_PIPELINE_TYPES", "")
    if raw:
        return [t.strip() for t in raw.split(",") if t.strip()]
    return []
