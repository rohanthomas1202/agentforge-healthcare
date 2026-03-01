"""FastAPI routes for the AgentForge Healthcare API."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from langchain_core.messages import HumanMessage, ToolMessage
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from fastapi.responses import StreamingResponse

from app.agent.graph import run_agent, run_agent_stream
from app.api.auth import verify_api_key
from app.config import settings
from app.database import (
    delete_conversation,
    get_connection,
    get_conversation_metadata,
    list_conversations,
    load_messages,
)
from app.fhir_client import fhir_client
from app.observability import get_metrics, record_feedback

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

# Unauthenticated router for health checks (needed by Railway healthcheck)
health_router = APIRouter()

# Authenticated router for all other endpoints
router = APIRouter(dependencies=[Depends(verify_api_key)])


# --- Request / Response Models ---


class ChatRequest(BaseModel):
    """User message to the agent."""

    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Agent response with metadata."""

    response: str
    conversation_id: str
    tool_calls: list[dict] = []
    confidence: Optional[float] = None
    disclaimers: list[str] = []
    verification: dict = {}
    token_usage: dict = {}
    latency_ms: Optional[float] = None


class FeedbackRequest(BaseModel):
    """User feedback on a conversation."""

    conversation_id: str
    rating: str  # "up" or "down"
    comment: Optional[str] = None


# --- Health Endpoints (unauthenticated) ---


@health_router.get("/health")
async def health_check():
    """Health check endpoint — also verifies SQLite connectivity."""
    db_ok = False
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        db_ok = True
    except Exception as e:
        logger.error("Health check DB failure: %s", e)

    status = "ok" if db_ok else "degraded"
    return {"status": status, "service": "agentforge-healthcare", "database": "ok" if db_ok else "error"}


@health_router.get("/health/ready")
async def readiness_check():
    """Readiness probe — checks DB connectivity and basic config."""
    checks: dict[str, str] = {}

    try:
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    config_issues = []
    if not settings.anthropic_api_key and not settings.openai_api_key:
        config_issues.append("No LLM API key configured")
    checks["config"] = f"warning: {'; '.join(config_issues)}" if config_issues else "ok"

    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "ready" if all_ok else "not_ready", "checks": checks}


# --- Authenticated Endpoints ---


@router.get("/health/fhir")
@limiter.limit("30/minute")
async def fhir_health_check(request: Request):
    """Check if OpenEMR FHIR API is reachable."""
    try:
        result = await fhir_client.get("metadata")
        resource_types = []
        for rest in result.get("rest", []):
            for resource in rest.get("resource", []):
                resource_types.append(resource.get("type"))
        return {
            "status": "ok",
            "fhir_version": result.get("fhirVersion"),
            "resource_count": len(resource_types),
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute")
async def chat(request: Request, chat_request: ChatRequest):
    """Send a message to the healthcare agent and get a response."""
    logger.info(
        "Chat request",
        extra={"operation": "conversation_message", "conversation_id": chat_request.conversation_id or "new"},
    )
    result = await run_agent(chat_request.message, chat_request.conversation_id)
    return result


@router.post("/chat/stream")
@limiter.limit("10/minute")
async def chat_stream(request: Request, chat_request: ChatRequest):
    """Stream agent response as Server-Sent Events."""
    logger.info(
        "Chat stream request",
        extra={"operation": "conversation_stream", "conversation_id": chat_request.conversation_id or "new"},
    )
    return StreamingResponse(
        run_agent_stream(chat_request.message, chat_request.conversation_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/feedback")
@limiter.limit("30/minute")
async def submit_feedback(request: Request, feedback_request: FeedbackRequest):
    """Submit thumbs-up / thumbs-down feedback for a conversation."""
    record_feedback(feedback_request.conversation_id, feedback_request.rating, feedback_request.comment)
    return {"status": "ok"}


@router.get("/metrics")
@limiter.limit("30/minute")
async def metrics(request: Request):
    """Return aggregated observability metrics."""
    return get_metrics()


# --- Conversation History Endpoints ---


class ConversationSummary(BaseModel):
    """Summary of a conversation for the sidebar list."""

    id: str
    title: str
    updated_at: float


class ConversationHistory(BaseModel):
    """Full conversation history for loading a past chat."""

    id: str
    title: str
    messages: list[dict]


@router.get("/conversations", response_model=list[ConversationSummary])
@limiter.limit("30/minute")
async def get_conversations(request: Request):
    """List recent conversations, newest first."""
    return list_conversations(limit=50)


@router.get("/conversations/{conversation_id}", response_model=ConversationHistory)
@limiter.limit("30/minute")
async def get_conversation(request: Request, conversation_id: str):
    """Load full message history for a conversation."""
    logger.info(
        "Conversation history accessed",
        extra={"operation": "conversation_read", "conversation_id": conversation_id},
    )
    meta = get_conversation_metadata(conversation_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = load_messages(conversation_id)
    frontend_messages = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            continue
        role = "user" if isinstance(msg, HumanMessage) else "assistant"
        frontend_messages.append({"role": role, "content": msg.content})

    return {
        "id": conversation_id,
        "title": meta["title"],
        "messages": frontend_messages,
    }


@router.delete("/conversations/{conversation_id}")
@limiter.limit("30/minute")
async def remove_conversation(request: Request, conversation_id: str):
    """Delete a conversation and its messages."""
    logger.info(
        "Conversation deleted",
        extra={"operation": "conversation_delete", "conversation_id": conversation_id},
    )
    delete_conversation(conversation_id)
    return {"status": "ok"}
