"""In-memory observability store for request metrics and user feedback."""

from __future__ import annotations

import time
from typing import Any, Optional


# ── Request records ──────────────────────────────────────────────────────────

_requests: list[dict[str, Any]] = []


def record_request(
    conversation_id: str,
    latency_ms: float,
    token_usage: dict[str, int],
    tool_calls: list[dict],
    error: Optional[str] = None,
) -> None:
    """Record metrics for a single agent request."""
    _requests.append({
        "conversation_id": conversation_id,
        "timestamp": time.time(),
        "latency_ms": round(latency_ms, 1),
        "token_usage": token_usage,
        "tool_calls": [tc["tool"] for tc in tool_calls],
        "error": error,
    })


# ── Feedback ─────────────────────────────────────────────────────────────────

_feedback: list[dict[str, Any]] = []


def record_feedback(
    conversation_id: str,
    rating: str,
    comment: Optional[str] = None,
) -> None:
    """Store a thumbs-up / thumbs-down rating for a conversation."""
    _feedback.append({
        "conversation_id": conversation_id,
        "rating": rating,
        "comment": comment,
        "timestamp": time.time(),
    })


# ── Aggregated metrics ───────────────────────────────────────────────────────

def get_metrics() -> dict[str, Any]:
    """Return aggregated observability metrics."""
    total = len(_requests)

    # Feedback (always computed, even with 0 requests)
    up = sum(1 for f in _feedback if f["rating"] == "up")
    down = sum(1 for f in _feedback if f["rating"] == "down")
    feedback = {"up": up, "down": down, "total": up + down}

    if total == 0:
        return {
            "total_requests": 0,
            "avg_latency_ms": 0,
            "total_tokens": {"input": 0, "output": 0, "total": 0},
            "tool_usage": {},
            "error_count": 0,
            "feedback": feedback,
        }

    # Latency
    latencies = [r["latency_ms"] for r in _requests]
    avg_latency = sum(latencies) / total

    # Token totals
    input_tokens = sum(r["token_usage"].get("input", 0) for r in _requests)
    output_tokens = sum(r["token_usage"].get("output", 0) for r in _requests)

    # Tool usage counts
    tool_counts: dict[str, int] = {}
    for r in _requests:
        for tool_name in r["tool_calls"]:
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

    # Errors
    error_count = sum(1 for r in _requests if r["error"])

    return {
        "total_requests": total,
        "avg_latency_ms": round(avg_latency, 1),
        "total_tokens": {
            "input": input_tokens,
            "output": output_tokens,
            "total": input_tokens + output_tokens,
        },
        "tool_usage": tool_counts,
        "error_count": error_count,
        "feedback": feedback,
    }
