"""Observability store — persists request metrics and feedback to SQLite."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from app.database import get_connection

logger = logging.getLogger(__name__)


# ── Request records ──────────────────────────────────────────────────────────


def record_request(
    conversation_id: str,
    latency_ms: float,
    token_usage: dict[str, int],
    tool_calls: list[dict],
    error: Optional[str] = None,
) -> None:
    """Record metrics for a single agent request."""
    now = time.time()
    tool_names = json.dumps([tc["tool"] for tc in tool_calls])
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO request_logs
                   (conversation_id, timestamp, latency_ms,
                    input_tokens, output_tokens, tool_calls, error, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    conversation_id,
                    now,
                    round(latency_ms, 1),
                    token_usage.get("input", 0),
                    token_usage.get("output", 0),
                    tool_names,
                    error,
                    now,
                ),
            )
    except Exception:
        logger.exception("Failed to persist request metrics")


# ── Feedback ─────────────────────────────────────────────────────────────────


def record_feedback(
    conversation_id: str,
    rating: str,
    comment: Optional[str] = None,
) -> None:
    """Store a thumbs-up / thumbs-down rating for a conversation."""
    now = time.time()
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO feedback_logs
                   (conversation_id, rating, comment, timestamp)
                   VALUES (?, ?, ?, ?)""",
                (conversation_id, rating, comment, now),
            )
    except Exception:
        logger.exception("Failed to persist feedback")


# ── Aggregated metrics ───────────────────────────────────────────────────────


def get_metrics() -> dict[str, Any]:
    """Return aggregated observability metrics from SQLite."""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS total, COALESCE(AVG(latency_ms), 0) AS avg_lat "
                "FROM request_logs"
            ).fetchone()
            total = row["total"]
            avg_latency = round(row["avg_lat"], 1)

            tok = conn.execute(
                "SELECT COALESCE(SUM(input_tokens), 0) AS inp, "
                "       COALESCE(SUM(output_tokens), 0) AS outp "
                "FROM request_logs"
            ).fetchone()
            input_tokens = tok["inp"]
            output_tokens = tok["outp"]

            err = conn.execute(
                "SELECT COUNT(*) AS cnt FROM request_logs WHERE error IS NOT NULL"
            ).fetchone()
            error_count = err["cnt"]

            # Tool usage counts
            tool_counts: dict[str, int] = {}
            rows = conn.execute("SELECT tool_calls FROM request_logs").fetchall()
            for r in rows:
                try:
                    names = json.loads(r["tool_calls"])
                    for name in names:
                        tool_counts[name] = tool_counts.get(name, 0) + 1
                except (json.JSONDecodeError, TypeError):
                    continue

            fb = conn.execute(
                "SELECT "
                "  SUM(CASE WHEN rating = 'up' THEN 1 ELSE 0 END) AS up, "
                "  SUM(CASE WHEN rating = 'down' THEN 1 ELSE 0 END) AS down, "
                "  COUNT(*) AS total "
                "FROM feedback_logs"
            ).fetchone()
            feedback = {
                "up": fb["up"] or 0,
                "down": fb["down"] or 0,
                "total": fb["total"] or 0,
            }

        return {
            "total_requests": total,
            "avg_latency_ms": avg_latency,
            "total_tokens": {
                "input": input_tokens,
                "output": output_tokens,
                "total": input_tokens + output_tokens,
            },
            "tool_usage": tool_counts,
            "error_count": error_count,
            "feedback": feedback,
        }
    except Exception:
        logger.exception("Failed to query metrics")
        return {
            "total_requests": 0,
            "avg_latency_ms": 0,
            "total_tokens": {"input": 0, "output": 0, "total": 0},
            "tool_usage": {},
            "error_count": 0,
            "feedback": {"up": 0, "down": 0, "total": 0},
        }
