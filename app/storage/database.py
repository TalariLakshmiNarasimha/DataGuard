"""SQLAlchemy engine and session management."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger("dataguard.storage")

_SCHEMA_FILE = Path(__file__).parent / "schema.sql"


def get_engine(database_url: str) -> Engine:
    """Create and return a SQLAlchemy engine.

    Parameters
    ----------
    database_url : str
        Full PostgreSQL connection URL.
    """
    return create_engine(database_url, pool_pre_ping=True, pool_size=5)


def get_session_factory(engine: Engine) -> sessionmaker:
    """Return a ``sessionmaker`` bound to *engine*."""
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_schema(engine: Engine) -> None:
    """Execute the DDL schema script to create tables if they don't exist.

    Parameters
    ----------
    engine : Engine
        SQLAlchemy engine connected to the target database.
    """
    ddl = _SCHEMA_FILE.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text(ddl))
    logger.info("Database schema initialized.")
