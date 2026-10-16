"""Individual data-quality validation rules.

Each rule is a callable that receives a single row (dict) and the set
of allowed statuses, and returns ``None`` if the row passes or a
human-readable rejection reason string if it fails.

Rules are kept as small, pure functions so they can be unit-tested
independently of the database or file system.
"""

from __future__ import annotations

from datetime import datetime
from typing import Sequence


# ---------------------------------------------------------------------------
# Rule functions
# ---------------------------------------------------------------------------

def check_order_id(row: dict, **_kw) -> str | None:
    """``order_id`` must be a non-empty string."""
    val = str(row.get("order_id", "")).strip()
    if not val:
        return "order_id is missing or empty"
    return None


def check_customer_id(row: dict, **_kw) -> str | None:
    """``customer_id`` must not be blank."""
    val = str(row.get("customer_id", "")).strip()
    if not val:
        return "customer_id is missing or empty"
    return None


def check_order_date(row: dict, **_kw) -> str | None:
    """``order_date`` must parse as a valid date (YYYY-MM-DD)."""
    val = str(row.get("order_date", "")).strip()
    if not val:
        return "order_date is missing or empty"
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            datetime.strptime(val, fmt)
            return None
        except ValueError:
            continue
    return f"order_date '{val}' is not a valid date"


def check_product(row: dict, **_kw) -> str | None:
    """``product`` must not be blank."""
    val = str(row.get("product", "")).strip()
    if not val:
        return "product is missing or empty"
    return None


def check_quantity(row: dict, **_kw) -> str | None:
    """``quantity`` must be an integer > 0."""
    val = str(row.get("quantity", "")).strip()
    if not val:
        return "quantity is missing or empty"
    try:
        q = int(float(val))
        if q <= 0:
            return f"quantity must be > 0, got {q}"
        if float(val) != q:
            return f"quantity must be a whole number, got '{val}'"
    except (ValueError, TypeError):
        return f"quantity '{val}' is not a valid integer"
    return None


def check_unit_price(row: dict, **_kw) -> str | None:
    """``unit_price`` must be numeric and >= 0."""
    val = str(row.get("unit_price", "")).strip()
    if not val:
        return "unit_price is missing or empty"
    try:
        price = float(val)
        if price < 0:
            return f"unit_price must be >= 0, got {price}"
    except (ValueError, TypeError):
        return f"unit_price '{val}' is not a valid number"
    return None


def check_status(row: dict, allowed_statuses: Sequence[str] = (), **_kw) -> str | None:
    """``status`` must be one of the allowed values after normalization."""
    val = str(row.get("status", "")).strip().upper()
    if not val:
        return "status is missing or empty"
    if val not in allowed_statuses:
        return f"status '{val}' is not allowed (expected one of {list(allowed_statuses)})"
    return None


# ---------------------------------------------------------------------------
# Registry of all rules (order matters for readability of rejection reasons)
# ---------------------------------------------------------------------------

ALL_RULES = [
    check_order_id,
    check_customer_id,
    check_order_date,
    check_product,
    check_quantity,
    check_unit_price,
    check_status,
]
