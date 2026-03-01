"""SQLite persistence layer for conversation history."""

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from typing import Optional

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    messages_from_dict,
    messages_to_dict,
)

from app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    message_data TEXT,
    created_at REAL NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);

CREATE TABLE IF NOT EXISTS request_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    latency_ms REAL NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    tool_calls TEXT NOT NULL DEFAULT '[]',
    error TEXT,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_request_logs_conversation ON request_logs(conversation_id);
CREATE INDEX IF NOT EXISTS idx_request_logs_timestamp ON request_logs(timestamp);

CREATE TABLE IF NOT EXISTS feedback_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    rating TEXT NOT NULL,
    comment TEXT,
    timestamp REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_feedback_logs_conversation ON feedback_logs(conversation_id);
"""


@contextmanager
def get_connection():
    """Yield a SQLite connection with WAL mode and foreign keys enabled."""
    db_path = settings.database_path
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they don't exist. Safe to call multiple times."""
    with get_connection() as conn:
        conn.executescript(_SCHEMA)


def create_conversation(conversation_id: str, title: str = "") -> None:
    """Insert a new conversation record."""
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (conversation_id, title, now, now),
        )


def update_conversation_title(conversation_id: str, title: str) -> None:
    """Set the title for a conversation."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, time.time(), conversation_id),
        )


def list_conversations(limit: int = 50) -> list[dict]:
    """Return recent conversations ordered by most recently updated."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, title, updated_at FROM conversations ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [{"id": r["id"], "title": r["title"], "updated_at": r["updated_at"]} for r in rows]


def get_conversation_metadata(conversation_id: str) -> Optional[dict]:
    """Return conversation metadata or None if not found."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if row:
            return {"id": row["id"], "title": row["title"], "created_at": row["created_at"], "updated_at": row["updated_at"]}
        return None


def save_messages(conversation_id: str, messages: list) -> None:
    """Persist a full list of LangChain messages for a conversation.

    Uses DELETE + INSERT to replace all messages atomically.
    Also updates the conversation's updated_at timestamp.
    """
    serialized = messages_to_dict(messages)
    now = time.time()
    with get_connection() as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        for msg_dict in serialized:
            role = msg_dict.get("type", "unknown")
            content = msg_dict.get("data", {}).get("content", "")
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content, message_data, created_at) VALUES (?, ?, ?, ?, ?)",
                (conversation_id, role, content, json.dumps(msg_dict), now),
            )
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )


def load_messages(conversation_id: str) -> list:
    """Load and deserialize LangChain messages for a conversation."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT message_data FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
    if not rows:
        return []
    msg_dicts = []
    for row in rows:
        try:
            msg_dicts.append(json.loads(row["message_data"]))
        except (json.JSONDecodeError, TypeError):
            continue
    return messages_from_dict(msg_dicts)


def delete_conversation(conversation_id: str) -> None:
    """Delete a conversation and all its messages."""
    with get_connection() as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
