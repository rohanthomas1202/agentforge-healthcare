"""HTTP client for the AgentForge Healthcare API."""

from __future__ import annotations

import os

import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8004")

# Timeouts
CHAT_TIMEOUT = 90  # Agent may chain multiple tools
HEALTH_TIMEOUT = 5


def send_message(message: str, conversation_id: str | None = None) -> dict:
    """Send a chat message to the agent and return the full response.

    Returns:
        {
            "response": str,
            "conversation_id": str,
            "tool_calls": list[dict],
            "confidence": float | None,
            "disclaimers": list[str],
            "verification": dict,
        }
    """
    payload = {"message": message}
    if conversation_id:
        payload["conversation_id"] = conversation_id

    resp = requests.post(
        f"{API_BASE_URL}/api/chat",
        json=payload,
        timeout=CHAT_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def send_feedback(conversation_id: str, rating: str, comment: str | None = None) -> dict:
    """Submit thumbs-up / thumbs-down feedback for a conversation."""
    payload = {"conversation_id": conversation_id, "rating": rating}
    if comment:
        payload["comment"] = comment
    try:
        resp = requests.post(
            f"{API_BASE_URL}/api/feedback",
            json=payload,
            timeout=HEALTH_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def check_health() -> dict:
    """Check if the backend API is healthy.

    Returns:
        {"status": "ok", "service": "agentforge-healthcare"} on success,
        {"status": "error", "detail": str} on failure.
    """
    try:
        resp = requests.get(f"{API_BASE_URL}/api/health", timeout=HEALTH_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"status": "error", "detail": str(e)}
