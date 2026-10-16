"""SQLAlchemy engine and session management."""

from __future__ import annotations

import logging
import sqlite3
from decimal import Decimal
from pathlib import Path

# Register Decimal adapter for SQLite
sqlite3.register_adapter(Decimal, lambda d: float(d))

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger("dataguard.storage")

_SCHEMA_FILE = Path(__file__).parent / "schema.sql"


def get_engine(database_url: str) -> Engine:
    """Create and return a SQLAlchemy engine.

    Supports both PostgreSQL and SQLite.
    """
    if database_url.startswith("sqlite"):
        if "///" in database_url:
            path_part = database_url.split("///", 1)[1]
            if path_part and path_part != ":memory:":
                Path(path_part).parent.mkdir(parents=True, exist_ok=True)
        return create_engine(database_url, connect_args={"check_same_thread": False})
    return create_engine(database_url, pool_pre_ping=True, pool_size=5)


def get_session_factory(engine: Engine) -> sessionmaker:
    """Return a ``sessionmaker`` bound to *engine*."""
    return sessionmaker(bind=engine, expire_on_commit=False)


_SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS orders (
    order_id        TEXT PRIMARY KEY,
    customer_id     TEXT NOT NULL,
    order_date      DATE NOT NULL,
    product         TEXT NOT NULL,
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    unit_price      NUMERIC(12,2) NOT NULL CHECK (unit_price >= 0),
    total_amount    NUMERIC(14,2) NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('PENDING','SHIPPED','DELIVERED','CANCELLED')),
    source_file     TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id              TEXT PRIMARY KEY,
    source_file         TEXT NOT NULL,
    started_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at         TIMESTAMP,
    status              TEXT NOT NULL DEFAULT 'RUNNING'
                            CHECK (status IN ('RUNNING','SUCCESS','PARTIAL_SUCCESS','FAILED')),
    total_records       INTEGER NOT NULL DEFAULT 0,
    accepted_records    INTEGER NOT NULL DEFAULT 0,
    rejected_records    INTEGER NOT NULL DEFAULT 0,
    inserted_records    INTEGER NOT NULL DEFAULT 0,
    updated_records     INTEGER NOT NULL DEFAULT 0,
    error_message       TEXT
);

CREATE TABLE IF NOT EXISTS quarantined_records (
    quarantine_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              TEXT NOT NULL REFERENCES pipeline_runs(run_id),
    source_file         TEXT NOT NULL,
    source_row_number   INTEGER NOT NULL,
    raw_record          TEXT NOT NULL,
    rejection_reasons   TEXT NOT NULL,
    quarantined_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status     ON pipeline_runs (status);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started    ON pipeline_runs (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_quarantined_run_id       ON quarantined_records (run_id);
CREATE INDEX IF NOT EXISTS idx_orders_status            ON orders (status);
"""


def init_schema(engine: Engine) -> None:
    """Execute the DDL schema script to create tables if they don't exist.

    Parameters
    ----------
    engine : Engine
        SQLAlchemy engine connected to the target database.
    """
    if engine.dialect.name == "sqlite":
        with engine.begin() as conn:
            for statement in _SQLITE_DDL.strip().split(";"):
                stmt = statement.strip()
                if stmt:
                    conn.execute(text(stmt))
        logger.info("SQLite database schema initialized.")
    else:
        ddl = _SCHEMA_FILE.read_text(encoding="utf-8")
        with engine.begin() as conn:
            conn.execute(text(ddl))
        logger.info("PostgreSQL database schema initialized.")
