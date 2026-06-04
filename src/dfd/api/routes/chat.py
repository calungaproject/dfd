"""Chat session and message endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from dfd.api.chatbot.engine import chat_completion_stream
from dfd.common import claude_client, db
from dfd.common.config import Settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


class CreateSessionRequest(BaseModel):
    title: str | None = None
    context_pipeline_run_id: str | None = None


class SendMessageRequest(BaseModel):
    content: str


@router.post("/sessions")
def create_session(req: CreateSessionRequest):
    """Create a new chat session."""
    session_id = db.create_chat_session(
        title=req.title,
        context_pipeline_run_id=req.context_pipeline_run_id,
    )
    return {"session_id": session_id}


@router.get("/sessions")
def list_sessions(limit: int = 20):
    """List recent chat sessions."""
    sessions = db.get_chat_sessions(limit=limit)
    return {"sessions": sessions}


@router.get("/sessions/{session_id}/messages")
def get_messages(session_id: str):
    """Get all messages for a chat session."""
    messages = db.get_chat_messages(session_id)
    return {"messages": messages}


@router.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, req: SendMessageRequest):
    """Send a message and stream the response via SSE."""
    if not req.content.strip():
        raise HTTPException(
            status_code=400,
            detail="Message content cannot be empty",
        )

    settings = Settings()
    claude_client.init_client(settings)

    return StreamingResponse(
        chat_completion_stream(
            session_id, req.content.strip(), settings
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
