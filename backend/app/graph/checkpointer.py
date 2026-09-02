"""
PostgreSQL checkpointer for LangGraph using AsyncConnectionPool.

Wraps LangGraph's AsyncPostgresSaver with an AsyncConnectionPool from psycopg_pool.
This maintains a persistent connection pool across the application lifecycle.

Thread ID convention:  "{tenant_id}:{sender_phone}"
"""
from __future__ import annotations
import asyncio
import logging
import sys
from typing import Optional

# psycopg3 async cannot run on Windows' default ProactorEventLoop.
# Force the selector loop (also the default on Linux/macOS) so the LangGraph
# PostgreSQL checkpointer works in dev on Windows.
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass  # Python 3.16+ removed the policy API — loop_factory is preferred there

from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[AsyncConnectionPool] = None
_checkpointer: Optional[AsyncPostgresSaver] = None


def _build_psycopg_url(sqlalchemy_url: str) -> str:
    """
    Convert SQLAlchemy asyncpg URL to psycopg3 URL.
    SQLAlchemy uses:  postgresql+asyncpg://user:pass@host/db
    psycopg3 needs:   postgresql://user:pass@host/db
    """
    url = sqlalchemy_url
    for prefix in ["postgresql+asyncpg://", "postgres+asyncpg://"]:
        if url.startswith(prefix):
            url = "postgresql://" + url[len(prefix):]
            break
    for prefix in ["postgresql+psycopg2://", "postgres+psycopg2://"]:
        if url.startswith(prefix):
            url = "postgresql://" + url[len(prefix):]
            break
    return url


async def get_checkpointer() -> AsyncPostgresSaver:
    """
    Return the singleton checkpointer, creating it on first call.
    Uses AsyncConnectionPool so connections stay open for the server lifetime.
    """
    global _pool, _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    psycopg_url = _build_psycopg_url(settings.DATABASE_URL)
    logger.info("[Checkpointer] Initializing PostgreSQL connection pool for LangGraph...")

    _pool = AsyncConnectionPool(conninfo=psycopg_url, max_size=10, open=False, kwargs={"autocommit": True})
    await _pool.open()

    saver = AsyncPostgresSaver(_pool)
    await saver.setup()  # Auto-creates the checkpoint tables if not existing

    _checkpointer = saver
    logger.info("[Checkpointer] LangGraph PostgreSQL checkpointer successfully initialized and ready.")
    return _checkpointer


async def close_checkpointer() -> None:
    """Close the underlying connection pool on server shutdown."""
    global _pool, _checkpointer
    if _pool is not None:
        await _pool.close()
        _pool = None
        _checkpointer = None
        logger.info("[Checkpointer] PostgreSQL connection pool closed.")


def make_thread_config(tenant_id: str, sender_phone: str) -> dict:
    """
    Build the LangGraph config dict for a specific conversation thread.
    Each (tenant, phone) pair gets its own isolated state checkpoint.
    """
    thread_id = f"{tenant_id}:{sender_phone}"
    return {"configurable": {"thread_id": thread_id}}
