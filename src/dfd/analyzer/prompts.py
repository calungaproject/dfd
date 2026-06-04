"""System prompts and tool schemas for the multi-agent pipeline.

Each function returns a list of content blocks for Claude's `system` parameter.
Taxonomy blocks include cache_control for batch cost savings.
Agent prompts are loaded from markdown files under src/dfd/prompts/agents/.
"""

from __future__ import annotations

from pathlib import Path

from dfd.common.taxonomy import render_taxonomy_markdown

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts" / "agents"

_file_cache: dict[str, str] = {}


def _load_text(path: Path) -> str:
    key = str(path)
    if key not in _file_cache:
        if not path.is_file():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        _file_cache[key] = path.read_text()
    return _file_cache[key]


def _get_agent_prompt(name: str) -> str:
    return _load_text(_PROMPTS_DIR / f"{name}.md")


# -- Tool schemas --

SELECT_SPECIALISTS_TOOL = {
    "name": "select_specialists",
    "description": (
        "Select which specialist agents to invoke for deeper analysis. "
        "Based on your initial triage, choose 0-2 specialists."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "specialists": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["log_analyst", "historical_analyst"],
                },
                "description": "Which specialists to invoke (empty = manager handles alone)",
            },
            "initial_classification": {
                "type": "string",
                "description": "Your initial best guess at root_cause (snake_case)",
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
            },
            "reasoning": {
                "type": "string",
                "description": "Why you chose these specialists (or none)",
            },
        },
        "required": ["specialists", "initial_classification", "confidence", "reasoning"],
    },
}

SUBMIT_ANALYSIS_TOOL = {
    "name": "submit_analysis",
    "description": "Submit the final structured analysis after reviewing all board entries.",
    "input_schema": {
        "type": "object",
        "properties": {
            "root_cause": {
                "type": "string",
                "description": "snake_case taxonomy ID for the root cause",
            },
            "category": {
                "type": "string",
                "enum": ["build", "infra", "unknown"],
            },
            "confidence": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
            },
            "alternative_root_cause": {
                "type": "string",
                "description": "Second-best classification (required if confidence < 80)",
            },
            "alternative_confidence": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
            },
            "ambiguity_note": {
                "type": "string",
                "description": "Explanation of ambiguity (required if confidence < 80)",
            },
            "failed_task": {
                "type": "string",
                "description": "Name of the failed Tekton task",
            },
            "failed_step": {
                "type": "string",
                "description": "Name of the failed step within the task",
            },
            "package_name": {
                "type": "string",
                "description": "Python package being built/tested, or N/A",
            },
            "error_message": {
                "type": "string",
                "description": "One-line error message",
            },
            "evidence": {
                "type": "string",
                "description": "5-15 key log lines that led to the classification",
            },
            "details": {
                "type": "string",
                "description": "1-3 sentences explaining what happened",
            },
            "suggested_action": {
                "type": "string",
                "description": "1-2 sentences on what to investigate or fix",
            },
            "remediation": {
                "type": "string",
                "description": (
                    "Concrete fix or remediation steps. Use 'N/A' for transient "
                    "infrastructure failures."
                ),
            },
        },
        "required": [
            "root_cause", "category", "confidence",
            "failed_task", "failed_step", "error_message",
            "evidence", "details", "suggested_action", "remediation",
        ],
    },
}

PROPOSE_RULE_TOOL = {
    "name": "propose_rule",
    "description": (
        "Propose a new taxonomy rule for a recurring failure pattern. "
        "Only when you've identified a clear pattern not in the taxonomy."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "root_cause": {
                "type": "string",
                "description": "snake_case ID (3-51 chars)",
            },
            "category": {
                "type": "string",
                "enum": ["build", "infra", "unknown"],
            },
            "error_signature": {
                "type": "string",
                "description": "Brief description of the error pattern (>= 10 chars)",
            },
            "priority_rule": {
                "type": "string",
                "description": "Rule: If {condition} -> `snake_case_id`",
            },
            "investigation_recipe": {
                "type": "string",
                "description": (
                    "Step-by-step recipe with concrete regex patterns. "
                    "Must be precise enough for any agent to reach the same classification."
                ),
            },
            "reasoning": {
                "type": "string",
                "description": "Why this is a distinct, recurring pattern",
            },
        },
        "required": [
            "root_cause", "category", "error_signature", "priority_rule",
            "investigation_recipe", "reasoning",
        ],
    },
}


# -- System prompts --


def manager_triage_prompt(pipeline_type_id: str) -> list[dict]:
    taxonomy = render_taxonomy_markdown(pipeline_type_id)
    return [
        {
            "type": "text",
            "text": taxonomy,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": _get_agent_prompt("manager_triage"),
        },
    ]


def manager_synthesis_prompt(pipeline_type_id: str) -> list[dict]:
    taxonomy = render_taxonomy_markdown(pipeline_type_id)
    return [
        {
            "type": "text",
            "text": taxonomy,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": _get_agent_prompt("manager_synthesis"),
        },
    ]


def log_analyst_prompt() -> list[dict]:
    return [
        {
            "type": "text",
            "text": _get_agent_prompt("log_analyst"),
        },
    ]


def historical_analyst_prompt() -> list[dict]:
    return [
        {
            "type": "text",
            "text": _get_agent_prompt("historical_analyst"),
        },
    ]
