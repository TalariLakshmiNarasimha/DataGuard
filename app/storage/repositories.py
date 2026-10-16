"""Repository layer: persistence operations for orders, quarantine, and runs.

All SQL uses parameterized queries and transactions.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("dataguard.storage")


# ---------------------------------------------------------------
# Pipeline Runs
# ---------------------------------------------------------------

def create_run(session: Session, run_id: str, source_file: str) -> None:
    """Insert a new pipeline run record with status ``RUNNING``."""
    session.execute(
        text(
            """
            INSERT INTO pipeline_runs (run_id, source_file, started_at, status)
            VALUES (:run_id, :source_file, :started_at, 'RUNNING')
            """
        ),
        {"run_id": run_id, "source_file": source_file, "started_at": datetime.now(timezone.utc).replace(tzinfo=None)},
    )
    session.commit()
    logger.info("Pipeline run %s created.", run_id)


def finish_run(
    session: Session,
    run_id: str,
    *,
    status: str,
    total_records: int,
    accepted_records: int,
    rejected_records: int,
    inserted_records: int,
    updated_records: int,
    error_message: str | None = None,
) -> None:
    """Update a pipeline run with final outcome metrics."""
    session.execute(
        text(
            """
            UPDATE pipeline_runs
            SET finished_at       = :finished_at,
                status            = :status,
                total_records     = :total_records,
                accepted_records  = :accepted_records,
                rejected_records  = :rejected_records,
                inserted_records  = :inserted_records,
                updated_records   = :updated_records,
                error_message     = :error_message
            WHERE run_id = :run_id
            """
        ),
        {
            "run_id": run_id,
            "finished_at": datetime.now(timezone.utc).replace(tzinfo=None),
            "status": status,
            "total_records": total_records,
            "accepted_records": accepted_records,
            "rejected_records": rejected_records,
            "inserted_records": inserted_records,
            "updated_records": updated_records,
            "error_message": error_message,
        },
    )
    session.commit()
    logger.info("Pipeline run %s finished with status %s.", run_id, status)


# ---------------------------------------------------------------
# Quarantined Records
# ---------------------------------------------------------------

def insert_quarantined_records(
    session: Session,
    records: list[dict[str, Any]],
) -> int:
    """Batch-insert rejected records into the quarantine table.

    Compatible with both PostgreSQL (JSONB) and SQLite (TEXT).
    Returns the number of rows inserted.
    """
    if not records:
        return 0

    now_val = datetime.now(timezone.utc).replace(tzinfo=None)
    records_to_insert = [
        {
            **rec,
            "quarantined_at": now_val,
            "raw_record": json.dumps(rec["raw_record"]) if not isinstance(rec["raw_record"], str) else rec["raw_record"],
            "rejection_reasons": json.dumps(rec["rejection_reasons"]) if not isinstance(rec["rejection_reasons"], str) else rec["rejection_reasons"],
        }
        for rec in records
    ]

    is_sqlite = session.bind is not None and session.bind.dialect.name == "sqlite"

    if is_sqlite:
        session.execute(
            text(
                """
                INSERT INTO quarantined_records
                    (run_id, source_file, source_row_number, raw_record,
                     rejection_reasons, quarantined_at)
                VALUES
                    (:run_id, :source_file, :source_row_number,
                     :raw_record,
                     :rejection_reasons,
                     :quarantined_at)
                """
            ),
            records_to_insert,
        )
    else:
        session.execute(
            text(
                """
                INSERT INTO quarantined_records
                    (run_id, source_file, source_row_number, raw_record,
                     rejection_reasons, quarantined_at)
                VALUES
                    (:run_id, :source_file, :source_row_number,
                     CAST(:raw_record AS JSONB),
                     CAST(:rejection_reasons AS JSONB),
                     :quarantined_at)
                """
            ),
            records_to_insert,
        )
    session.commit()
    logger.info("Quarantined %d records.", len(records))
    return len(records)


# ---------------------------------------------------------------
# Orders (upsert / idempotent)
# ---------------------------------------------------------------

def upsert_orders(
    session: Session,
    records: list[dict[str, Any]],
) -> tuple[int, int]:
    """Upsert validated order records into the ``orders`` table.

    Uses ``ON CONFLICT ... DO UPDATE`` to ensure idempotent
    behavior across both PostgreSQL and SQLite.

    Returns
    -------
    tuple[int, int]
        ``(inserted_count, updated_count)``
    """
    if not records:
        return 0, 0

    inserted = 0
    updated = 0
    now_val = datetime.now(timezone.utc).replace(tzinfo=None)

    # Collect all order_ids to check which already exist
    order_ids = [rec["order_id"] for rec in records]

    is_sqlite = session.bind is not None and session.bind.dialect.name == "sqlite"

    if is_sqlite:
        placeholders = ", ".join(f":id_{i}" for i in range(len(order_ids)))
        params = {f"id_{i}": oid for i, oid in enumerate(order_ids)}
        existing_rows = session.execute(
            text(f"SELECT order_id FROM orders WHERE order_id IN ({placeholders})"),
            params,
        ).fetchall()
    else:
        existing_rows = session.execute(
            text("SELECT order_id FROM orders WHERE order_id = ANY(:ids)"),
            {"ids": order_ids},
        ).fetchall()

    existing_ids = {row[0] for row in existing_rows}

    for rec in records:
        is_update = rec["order_id"] in existing_ids

        row_params = dict(rec)
        row_params["now"] = now_val
        if is_sqlite:
            for k in ("unit_price", "total_amount"):
                if k in row_params and hasattr(row_params[k], "__float__"):
                    row_params[k] = float(row_params[k])

        session.execute(
            text(
                """
                INSERT INTO orders
                    (order_id, customer_id, order_date, product, quantity,
                     unit_price, total_amount, status, source_file,
                     created_at, updated_at)
                VALUES
                    (:order_id, :customer_id, :order_date, :product, :quantity,
                     :unit_price, :total_amount, :status, :source_file,
                     :now, :now)
                ON CONFLICT (order_id) DO UPDATE SET
                    customer_id  = EXCLUDED.customer_id,
                    order_date   = EXCLUDED.order_date,
                    product      = EXCLUDED.product,
                    quantity     = EXCLUDED.quantity,
                    unit_price   = EXCLUDED.unit_price,
                    total_amount = EXCLUDED.total_amount,
                    status       = EXCLUDED.status,
                    source_file  = EXCLUDED.source_file,
                    updated_at   = :now
                """
            ),
            row_params,
        )

        if is_update:
            updated += 1
        else:
            inserted += 1
            existing_ids.add(rec["order_id"])

    session.commit()
    logger.info("Upserted orders: %d inserted, %d updated.", inserted, updated)
    return inserted, updated

