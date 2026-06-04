"""Chatbot engine — Claude API tool-use loop with SSE streaming.

Handles multi-turn conversation with tool-use loop, streaming
responses via Server-Sent Events, and cost tracking.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from dfd.api.chatbot.prompts import CHATBOT_SYSTEM_PROMPT
from dfd.api.chatbot.tools import CHATBOT_TOOLS, execute_tool
from dfd.common import claude_client, db
from dfd.common.config import Settings
from dfd.common.models import InvocationType

logger = logging.getLogger(__name__)

MAX_TOOL_LOOPS = 15


async def chat_completion_stream(
    session_id: str,
    user_message: str,
    settings: Settings,
) -> AsyncIterator[str]:
    """Run chat completion and yield SSE events.

    Events:
    - tool_call: A tool is being executed
    - tool_result: Tool execution result (truncated)
    - text_delta: Partial text output from Claude
    - done: Final response with cost/token metadata
    - error: An error occurred
    """
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _produce() -> None:
        history = db.get_chat_messages(session_id)
        is_first_exchange = len(history) == 0
        messages = _build_messages(history, user_message)
        db.insert_chat_message(session_id, "user", user_message)

        tool_calls_log: list[dict[str, Any]] = []
        all_text_parts: list[str] = []
        total_cost = 0.0
        total_tokens = 0

        try:
            iteration = 0
            while iteration < MAX_TOOL_LOOPS:
                iteration += 1

                response = await _call_claude_with_keepalive(
                    queue,
                    system=[{
                        "type": "text",
                        "text": CHATBOT_SYSTEM_PROMPT,
                    }],
                    messages=messages,
                    model=settings.claude_model,
                    max_tokens=8000,
                    tools=CHATBOT_TOOLS,
                    thinking_budget=4000,
                )

                cost = claude_client.calculate_cost(
                    response.usage, settings.claude_model
                )
                total_cost += cost
                total_tokens += (
                    response.usage.input_tokens
                    + response.usage.output_tokens
                )

                cost_entry = claude_client.make_cost_entry(
                    response,
                    model=settings.claude_model,
                    invocation_type=InvocationType.CHAT,
                    chat_session_id=session_id,
                )
                db.insert_cost_entry(cost_entry)

                if (
                    response.stop_reason == "tool_use"
                    and response.tool_use
                ):
                    assistant_content = _build_assistant_content(
                        response
                    )
                    if response.text:
                        all_text_parts.append(response.text)
                        await queue.put(_sse_event({
                            "type": "text_delta",
                            "text": response.text,
                        }))

                    tool_results: list[dict[str, Any]] = []
                    for tool in response.tool_use:
                        assistant_content.append({
                            "type": "tool_use",
                            "id": tool.id,
                            "name": tool.name,
                            "input": tool.input,
                        })

                        await queue.put(_sse_event({
                            "type": "tool_call",
                            "name": tool.name,
                            "input": tool.input,
                        }))

                        result = execute_tool(
                            tool.name, tool.input, settings
                        )

                        tool_calls_log.append({
                            "name": tool.name,
                            "input": tool.input,
                            "result_preview": (
                                result[:200] if result else ""
                            ),
                        })

                        await queue.put(_sse_event({
                            "type": "tool_result",
                            "name": tool.name,
                            "result": (
                                result[:500] if result else ""
                            ),
                        }))

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool.id,
                            "content": result,
                        })

                    messages.append({
                        "role": "assistant",
                        "content": assistant_content,
                    })
                    messages.append({
                        "role": "user",
                        "content": tool_results,
                    })
                    continue

                if response.text:
                    all_text_parts.append(response.text)
                    await queue.put(_sse_event({
                        "type": "text_delta",
                        "text": response.text,
                    }))

                final_text = (
                    "\n\n".join(all_text_parts)
                    if all_text_parts
                    else response.text
                )

                db.insert_chat_message(
                    session_id,
                    "assistant",
                    final_text,
                    tool_calls=(
                        tool_calls_log if tool_calls_log else None
                    ),
                    cost_usd=total_cost,
                    tokens_used=total_tokens,
                )

                await queue.put(_sse_event({
                    "type": "done",
                    "content": final_text,
                    "cost_usd": round(total_cost, 6),
                    "tokens_used": total_tokens,
                }))

                if is_first_exchange:
                    asyncio.create_task(
                        _generate_session_title(
                            session_id,
                            user_message,
                            final_text or "",
                        )
                    )
                return

            error_msg = (
                "Reached maximum tool-use iterations. "
                "Please try a simpler question."
            )
            db.insert_chat_message(session_id, "assistant", error_msg)
            await queue.put(_sse_event({
                "type": "error", "message": error_msg,
            }))

        except Exception as e:
            logger.exception(
                "Chat stream error for session %s", session_id
            )
            await queue.put(_sse_event({
                "type": "error", "message": str(e),
            }))
        finally:
            await queue.put(None)

    task = asyncio.create_task(_produce())
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
    finally:
        if not task.done():
            task.cancel()


async def _call_claude_with_keepalive(
    queue: asyncio.Queue[str | None],
    **kwargs: Any,
) -> Any:
    """Call claude_client.send_message in a thread,
    sending SSE keepalives every 10s."""
    api_task = asyncio.ensure_future(
        asyncio.to_thread(claude_client.send_message, **kwargs)
    )

    while not api_task.done():
        try:
            await asyncio.wait_for(
                asyncio.shield(api_task), timeout=10.0
            )
        except asyncio.TimeoutError:
            await queue.put(": keepalive\n\n")

    return api_task.result()


async def _generate_session_title(
    session_id: str,
    user_message: str,
    assistant_response: str,
) -> None:
    """Generate a short title for a new chat session."""
    try:
        prompt = (
            "Generate a very short title (max 6 words) for this "
            "chat. Return ONLY the title, no quotes.\n\n"
            f"User: {user_message[:300]}\n"
            f"Assistant: {assistant_response[:300]}"
        )
        response = await asyncio.to_thread(
            claude_client.send_message,
            system=[{
                "type": "text",
                "text": "You generate short chat titles.",
            }],
            messages=[{"role": "user", "content": prompt}],
            model="claude-haiku-4-5-20251001",
            max_tokens=30,
            thinking_budget=1024,
        )
        if response.text:
            title = response.text.strip().strip('"').strip("'")[:80]
            db.update_chat_session_title(session_id, title)
    except Exception:
        logger.debug(
            "Failed to generate title for %s",
            session_id,
            exc_info=True,
        )


def _build_messages(
    history: list[dict[str, Any]],
    new_user_message: str,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for msg in history:
        messages.append({
            "role": msg["role"],
            "content": msg["content"],
        })
    messages.append({"role": "user", "content": new_user_message})
    return messages


def _build_assistant_content(response: Any) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = []
    if response.thinking:
        block: dict[str, Any] = {
            "type": "thinking",
            "thinking": response.thinking,
        }
        if response.thinking_signature:
            block["signature"] = response.thinking_signature
        content.append(block)
    if response.text:
        content.append({"type": "text", "text": response.text})
    return content


def _sse_event(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data)}\n\n"
