"""FastAPI routes for the AgentForge Healthcare API."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.agent.graph import run_agent
from app.fhir_client import fhir_client
from app.observability import get_metrics, record_feedback

router = APIRouter()


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


# --- Endpoints ---


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "agentforge-healthcare"}


@router.get("/health/fhir")
async def fhir_health_check():
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
async def chat(request: ChatRequest):
    """Send a message to the healthcare agent and get a response."""
    result = await run_agent(request.message, request.conversation_id)
    return result


@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """Submit thumbs-up / thumbs-down feedback for a conversation."""
    record_feedback(request.conversation_id, request.rating, request.comment)
    return {"status": "ok"}


@router.get("/metrics")
async def metrics():
    """Return aggregated observability metrics."""
    return get_metrics()
