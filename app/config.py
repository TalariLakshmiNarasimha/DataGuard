"""Application configuration loaded from environment variables."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env file if present (never committed; .env.example is committed instead)
load_dotenv()


@dataclass(frozen=True)
class DatabaseConfig:
    """PostgreSQL connection parameters."""

    host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5432")))
    name: str = field(default_factory=lambda: os.getenv("DB_NAME", "dataguard"))
    user: str = field(default_factory=lambda: os.getenv("DB_USER", "dataguard"))
    password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", "dataguard"))

    @property
    def url(self) -> str:
        """SQLAlchemy connection URL (credentials read from env vars or Streamlit secrets)."""
        raw_url = os.getenv("DATABASE_URL")
        if not raw_url:
            try:
                import streamlit as st
                raw_url = st.secrets.get("DATABASE_URL") or st.secrets.get("postgres", {}).get("url")
            except Exception:
                raw_url = None

        if raw_url:
            if raw_url.startswith("postgres://"):
                raw_url = raw_url.replace("postgres://", "postgresql+psycopg2://", 1)
            elif raw_url.startswith("postgresql://") and not raw_url.startswith("postgresql+psycopg2://"):
                raw_url = raw_url.replace("postgresql://", "postgresql+psycopg2://", 1)
            return raw_url

        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration."""

    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper()
    )
    batch_size: int = field(
        default_factory=lambda: int(os.getenv("BATCH_SIZE", "1000"))
    )
    data_dir: Path = field(
        default_factory=lambda: Path(os.getenv("DATA_DIR", "data"))
    )

    # Allowed order statuses after normalization
    ALLOWED_STATUSES: tuple[str, ...] = (
        "PENDING",
        "SHIPPED",
        "DELIVERED",
        "CANCELLED",
    )


def get_config() -> AppConfig:
    """Return a validated application configuration instance.

    Raises
    ------
    ValueError
        If any required configuration value is missing or invalid.
    """
    cfg = AppConfig()

    # Validate critical settings
    if not cfg.db.user:
        raise ValueError("DB_USER environment variable must be set.")
    if not cfg.db.password:
        raise ValueError("DB_PASSWORD environment variable must be set.")
    if not cfg.db.name:
        raise ValueError("DB_NAME environment variable must be set.")
    if cfg.batch_size < 1:
        raise ValueError("BATCH_SIZE must be >= 1.")

    return cfg
