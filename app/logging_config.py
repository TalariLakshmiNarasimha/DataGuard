"""Structured logging configuration for the DataGuard pipeline."""

import logging
import sys


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure and return the root application logger.

    Parameters
    ----------
    level : str
        Logging level name (e.g. ``"INFO"``, ``"DEBUG"``).

    Returns
    -------
    logging.Logger
        Configured logger instance named ``dataguard``.
    """
    logger = logging.getLogger("dataguard")
    logger.setLevel(getattr(logging, level, logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, level, logging.INFO))
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
