"""Record-level validator that applies all quality rules.

The validator iterates over rows, applies every rule to each row,
detects duplicate ``order_id`` values within the batch, and splits
the input into accepted and rejected sets.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Sequence

import pandas as pd

from app.quality.rules import ALL_RULES

logger = logging.getLogger("dataguard.quality")


def validate_dataframe(
    df: pd.DataFrame,
    allowed_statuses: Sequence[str],
    source_file: str,
    run_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate every row in *df* and split into accepted / rejected.

    Parameters
    ----------
    df : pd.DataFrame
        Raw DataFrame from CSV ingestion (must include ``_source_row_number``).
    allowed_statuses : Sequence[str]
        Normalized status values considered valid.
    source_file : str
        Filename (basename) of the source CSV for audit metadata.
    run_id : str
        Pipeline run identifier for quarantine records.

    Returns
    -------
    tuple[list[dict], list[dict]]
        ``(accepted_records, rejected_records)``

        *accepted_records* are dicts ready for transformation.

        *rejected_records* are dicts ready for quarantine persistence,
        each containing ``run_id``, ``source_file``,
        ``source_row_number``, ``raw_record`` (JSON string), and
        ``rejection_reasons`` (JSON list of strings).
    """
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    seen_order_ids: dict[str, int] = {}  # order_id -> first source row

    for _, row_series in df.iterrows():
        row = row_series.to_dict()
        source_row = int(row.get("_source_row_number", 0))
        reasons: list[str] = []

        # --- field-level rules ---
        for rule_fn in ALL_RULES:
            reason = rule_fn(row, allowed_statuses=allowed_statuses)
            if reason:
                reasons.append(reason)

        # --- duplicate detection within the batch ---
        oid = str(row.get("order_id", "")).strip()
        if oid:
            if oid in seen_order_ids:
                reasons.append(
                    f"Duplicate order_id '{oid}' within batch "
                    f"(first seen at row {seen_order_ids[oid]})"
                )
            else:
                seen_order_ids[oid] = source_row

        # --- classify ---
        # Build a clean copy without internal metadata for raw_record
        raw = {k: v for k, v in row.items() if not k.startswith("_")}

        if reasons:
            rejected.append(
                {
                    "run_id": run_id,
                    "source_file": source_file,
                    "source_row_number": source_row,
                    "raw_record": json.dumps(raw),
                    "rejection_reasons": json.dumps(reasons),
                }
            )
        else:
            row["_source_file"] = source_file
            accepted.append(row)

    logger.info(
        "Validation complete: %d accepted, %d rejected.",
        len(accepted),
        len(rejected),
    )
    return accepted, rejected
