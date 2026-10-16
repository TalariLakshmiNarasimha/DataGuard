"""Order record normalization and enrichment.

Transforms validated raw row dicts into clean records ready for
database insertion.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger("dataguard.transformations")

# Supported date formats (tried in order)
_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d")


def _parse_date(raw: str) -> datetime:
    """Parse a date string against known formats."""
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: '{raw}'")


def transform_record(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize and enrich a single validated order row.

    Parameters
    ----------
    row : dict
        A validated row dict from the CSV (all values are strings).

    Returns
    -------
    dict
        Cleaned record with correct Python types, ready for DB upsert.
    """
    order_id = str(row["order_id"]).strip()
    customer_id = str(row["customer_id"]).strip()
    order_date = _parse_date(str(row["order_date"]))
    product = str(row["product"]).strip()
    quantity = int(float(str(row["quantity"]).strip()))
    unit_price = Decimal(str(row["unit_price"]).strip())
    total_amount = Decimal(quantity) * unit_price
    status = str(row["status"]).strip().upper()
    source_file = row.get("_source_file", "")

    return {
        "order_id": order_id,
        "customer_id": customer_id,
        "order_date": order_date.date(),
        "product": product,
        "quantity": quantity,
        "unit_price": unit_price,
        "total_amount": total_amount,
        "status": status,
        "source_file": source_file,
    }


def transform_batch(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Transform a list of validated rows.

    Parameters
    ----------
    rows : list[dict]
        Validated row dicts.

    Returns
    -------
    list[dict]
        Transformed records.
    """
    transformed = []
    for row in rows:
        try:
            transformed.append(transform_record(row))
        except (ValueError, InvalidOperation, KeyError) as exc:
            # This should not happen for validated rows, but guard anyway
            logger.error("Transformation error on row %s: %s", row.get("order_id"), exc)
    logger.info("Transformed %d records.", len(transformed))
    return transformed
