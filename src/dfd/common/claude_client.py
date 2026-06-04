"""Anthropic SDK wrapper for DFD.

Provides a thin wrapper around AnthropicVertex for all agent communication.
No agent should import `anthropic` directly — all calls go through this module.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from anthropic import AnthropicVertex

from dfd.common.config import Settings
from dfd.common.models import CostEntry, InvocationType

logger = logging.getLogger(__name__)

_client: AnthropicVertex | None = None


def init_client(settings: Settings) -> None:
    """Initialize the global AnthropicVertex client."""
    global _client
    if _client is not None:
        return
    _client = AnthropicVertex(
        region=settings.google_cloud_region,
        project_id=settings.google_cloud_project,
    )
    logger.info(
        "AnthropicVertex client initialized (region=%s, project=%s)",
        settings.google_cloud_region,
        settings.google_cloud_project,
    )


def get_client() -> AnthropicVertex:
    if _client is None:
        raise RuntimeError("Claude client not initialized — call init_client() first")
    return _client


@dataclass
class ToolUseResult:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class UsageInfo:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass
class ClaudeResponse:
    thinking: str = ""
    thinking_signature: str = ""
    text: str = ""
    tool_use: list[ToolUseResult] = field(default_factory=list)
    stop_reason: str = ""
    usage: UsageInfo = field(default_factory=UsageInfo)
    duration_ms: int = 0


def send_message(
    *,
    system: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    model: str,
    max_tokens: int = 16000,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: dict[str, Any] | None = None,
    thinking_budget: int = 10000,
) -> ClaudeResponse:
    """Send a message to Claude via Vertex AI. Synchronous — use asyncio.to_thread()."""
    client = get_client()

    effective_max = max(max_tokens, thinking_budget + 1024)
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": effective_max,
        "system": system,
        "messages": messages,
        "thinking": {
            "type": "enabled",
            "budget_tokens": thinking_budget,
        },
    }
    if tools:
        kwargs["tools"] = tools
    if tool_choice:
        kwargs["tool_choice"] = tool_choice

    start = time.monotonic()
    response = client.messages.create(**kwargs)
    duration_ms = int((time.monotonic() - start) * 1000)

    result = ClaudeResponse(
        stop_reason=response.stop_reason or "",
        duration_ms=duration_ms,
    )

    for block in response.content:
        if block.type == "thinking":
            result.thinking += block.thinking
            if hasattr(block, "signature") and block.signature:
                result.thinking_signature = block.signature
        elif block.type == "text":
            result.text += block.text
        elif block.type == "tool_use":
            result.tool_use.append(
                ToolUseResult(id=block.id, name=block.name, input=block.input)
            )

    usage = response.usage
    result.usage = UsageInfo(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
    )

    logger.info(
        "Claude API: model=%s, in=%d, out=%d, cache_read=%d, cache_create=%d, "
        "duration=%dms, stop=%s",
        model,
        result.usage.input_tokens,
        result.usage.output_tokens,
        result.usage.cache_read_input_tokens,
        result.usage.cache_creation_input_tokens,
        duration_ms,
        result.stop_reason,
    )

    return result


# Vertex AI pricing per million tokens
PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_creation": 3.75,
    },
}

_DEFAULT_PRICING = {
    "input": 3.00,
    "output": 15.00,
    "cache_read": 0.30,
    "cache_creation": 3.75,
}


def calculate_cost(usage: UsageInfo, model: str) -> float:
    prices = PRICING.get(model, _DEFAULT_PRICING)
    cost = (
        (usage.input_tokens * prices["input"])
        + (usage.output_tokens * prices["output"])
        + (usage.cache_read_input_tokens * prices["cache_read"])
        + (usage.cache_creation_input_tokens * prices["cache_creation"])
    ) / 1_000_000
    return round(cost, 6)


def make_cost_entry(
    response: ClaudeResponse,
    *,
    model: str,
    invocation_type: InvocationType,
    analysis_run_id: int | None = None,
    pipeline_run_id: str | None = None,
    chat_session_id: str | None = None,
) -> CostEntry:
    return CostEntry(
        analysis_run_id=analysis_run_id,
        pipeline_run_id=pipeline_run_id,
        invocation_type=invocation_type,
        chat_session_id=chat_session_id,
        cost_usd=calculate_cost(response.usage, model),
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        cache_read_tokens=response.usage.cache_read_input_tokens,
        cache_creation_tokens=response.usage.cache_creation_input_tokens,
        duration_ms=response.duration_ms,
        model=model,
    )
