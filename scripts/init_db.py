"""Database initialization helper script.

Usage:
    python scripts/init_db.py

Creates the DataGuard PostgreSQL tables using the schema.sql DDL script.
Intended for first-time setup or to re-apply schema (idempotent).
"""

import sys
from pathlib import Path

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_config
from app.logging_config import setup_logging
from app.storage.database import get_engine, init_schema


def main() -> None:
    """Initialize database schema."""
    config = get_config()
    setup_logging(config.log_level)

    print(f"Connecting to database '{config.db.name}' on {config.db.host}:{config.db.port}...")
    engine = get_engine(config.db.url)
    init_schema(engine)
    print("Schema initialization complete.")


if __name__ == "__main__":
    main()
