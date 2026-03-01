"""HTTP client for the AgentForge Healthcare API."""

from __future__ import annotations

import json
import os
from collections.abc import Generator

import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")

# Timeouts
CHAT_TIMEOUT = 90  # Agent may chain multiple tools
HEALTH_TIMEOUT = 5


def _headers() -> dict[str, str]:
    """Build common request headers, including API key if set."""
    h: dict[str, str] = {}
    if API_KEY:
        h["X-API-Key"] = API_KEY
    return h


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
        headers=_headers(),
        timeout=CHAT_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def stream_message(
    message: str, conversation_id: str | None = None
) -> Generator[dict, None, None]:
    """Stream a chat response via SSE. Yields parsed event dicts.

    Each yielded dict has: {"event": str, "data": dict}
    Events: thinking, tool_call, token, done, error
    """
    payload: dict = {"message": message}
    if conversation_id:
        payload["conversation_id"] = conversation_id

    try:
        with requests.post(
            f"{API_BASE_URL}/api/chat/stream",
            json=payload,
            headers=_headers(),
            timeout=CHAT_TIMEOUT,
            stream=True,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                try:
                    parsed = json.loads(line[6:])
                    yield parsed
                except json.JSONDecodeError:
                    continue
    except requests.Timeout:
        yield {"event": "error", "data": {"message": "Request timed out."}}
    except requests.ConnectionError:
        yield {"event": "error", "data": {"message": "Could not connect to backend."}}
    except Exception as e:
        yield {"event": "error", "data": {"message": str(e)}}


def send_feedback(conversation_id: str, rating: str, comment: str | None = None) -> dict:
    """Submit thumbs-up / thumbs-down feedback for a conversation."""
    payload = {"conversation_id": conversation_id, "rating": rating}
    if comment:
        payload["comment"] = comment
    try:
        resp = requests.post(
            f"{API_BASE_URL}/api/feedback",
            json=payload,
            headers=_headers(),
            timeout=HEALTH_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def get_metrics() -> dict:
    """Fetch aggregated metrics from the backend."""
    try:
        resp = requests.get(
            f"{API_BASE_URL}/api/metrics",
            headers=_headers(),
            timeout=HEALTH_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def get_conversations() -> list[dict]:
    """Fetch list of recent conversations from backend."""
    try:
        resp = requests.get(
            f"{API_BASE_URL}/api/conversations",
            headers=_headers(),
            timeout=HEALTH_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def get_conversation_history(conversation_id: str) -> dict:
    """Fetch full message history for a conversation."""
    try:
        resp = requests.get(
            f"{API_BASE_URL}/api/conversations/{conversation_id}",
            headers=_headers(),
            timeout=HEALTH_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def delete_conversation(conversation_id: str) -> dict:
    """Delete a conversation."""
    try:
        resp = requests.delete(
            f"{API_BASE_URL}/api/conversations/{conversation_id}",
            headers=_headers(),
            timeout=HEALTH_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def check_health() -> dict:
    """Check if the backend API is healthy.

    Returns:
        {"status": "ok", "service": "agentforge-healthcare"} on success,
        {"status": "error", "detail": str} on failure.
    """
    try:
        resp = requests.get(
            f"{API_BASE_URL}/api/health",
            headers=_headers(),
            timeout=HEALTH_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"status": "error", "detail": str(e)}
