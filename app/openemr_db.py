"""Async MariaDB connection pool for custom tables (care gaps, formulary, labs).

These tables live in the same OpenEMR MariaDB database but are not part of
the FHIR API — they extend OpenEMR with application-specific data.

Connection details come from environment variables with sensible defaults
for the Docker Compose setup (mariadb host on internal network).
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import aiomysql

logger = logging.getLogger(__name__)

# Connection settings — match docker-compose.cloud.yml defaults
_DB_CONFIG = {
    "host": os.getenv("MARIADB_HOST", "mariadb"),
    "port": int(os.getenv("MARIADB_PORT", "3306")),
    "user": os.getenv("MARIADB_USER", "openemr"),
    "password": os.getenv("MARIADB_PASSWORD", "openemr"),
    "db": os.getenv("MARIADB_DATABASE", "openemr"),
    "autocommit": True,
}

_pool: aiomysql.Pool | None = None


async def get_pool() -> aiomysql.Pool:
    """Get or create the connection pool (lazy singleton)."""
    global _pool
    if _pool is None or _pool.closed:
        _pool = await aiomysql.create_pool(
            minsize=1,
            maxsize=5,
            **_DB_CONFIG,
        )
        logger.info("MariaDB connection pool created (%s:%s)", _DB_CONFIG["host"], _DB_CONFIG["port"])
    return _pool


@asynccontextmanager
async def get_cursor():
    """Context manager that yields a cursor from the pool."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            yield cur


async def fetch_all(sql: str, args: tuple = ()) -> list[dict[str, Any]]:
    """Execute a SELECT and return all rows as dicts."""
    async with get_cursor() as cur:
        await cur.execute(sql, args)
        return await cur.fetchall()


async def fetch_one(sql: str, args: tuple = ()) -> dict[str, Any] | None:
    """Execute a SELECT and return the first row as a dict."""
    async with get_cursor() as cur:
        await cur.execute(sql, args)
        return await cur.fetchone()


async def execute(sql: str, args: tuple = ()) -> int:
    """Execute an INSERT/UPDATE/DELETE and return affected row count."""
    async with get_cursor() as cur:
        await cur.execute(sql, args)
        return cur.rowcount


async def execute_returning_id(sql: str, args: tuple = ()) -> int:
    """Execute an INSERT and return the last inserted ID."""
    async with get_cursor() as cur:
        await cur.execute(sql, args)
        return cur.lastrowid


async def close_pool():
    """Close the connection pool (for graceful shutdown)."""
    global _pool
    if _pool and not _pool.closed:
        _pool.close()
        await _pool.wait_closed()
        _pool = None
        logger.info("MariaDB connection pool closed")
