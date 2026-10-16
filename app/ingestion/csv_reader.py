"""CSV reader for order data ingestion.

Reads a CSV file, validates the presence of required columns, and
returns a pandas DataFrame with source metadata attached.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger("dataguard.ingestion")

REQUIRED_COLUMNS: list[str] = [
    "order_id",
    "customer_id",
    "order_date",
    "product",
    "quantity",
    "unit_price",
    "status",
]


class IngestionError(Exception):
    """Raised when the input file cannot be ingested."""


def read_csv(file_path: str | Path) -> pd.DataFrame:
    """Read and minimally parse a CSV file of order data.

    Parameters
    ----------
    file_path : str or Path
        Path to the CSV file.

    Returns
    -------
    pd.DataFrame
        Raw DataFrame with an added ``_source_row_number`` column
        (1-indexed, matching the CSV line number excluding the header).

    Raises
    ------
    IngestionError
        If the file does not exist, is empty, is unreadable, or is
        missing required columns.
    """
    path = Path(file_path)

    if not path.exists():
        raise IngestionError(f"Input file not found: {path}")

    if path.stat().st_size == 0:
        raise IngestionError(f"Input file is empty: {path}")

    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
    except Exception as exc:
        raise IngestionError(f"Failed to read CSV file '{path}': {exc}") from exc

    if df.empty:
        raise IngestionError(f"Input file contains a header but no data rows: {path}")

    # Normalize column names to lower-case, stripped
    df.columns = [c.strip().lower() for c in df.columns]

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise IngestionError(
            f"Input file is missing required columns: {', '.join(missing)}"
        )

    # 1-indexed source row number (row 1 = first data row in CSV)
    df["_source_row_number"] = range(1, len(df) + 1)

    logger.info("Read %d rows from '%s'.", len(df), path.name)
    return df
