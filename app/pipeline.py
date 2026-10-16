"""Main ETL pipeline orchestrator.

Coordinates ingestion → validation → transformation → persistence
and tracks the pipeline run lifecycle.
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from pathlib import Path

from app.config import get_config
from app.ingestion.csv_reader import IngestionError, read_csv
from app.logging_config import setup_logging
from app.quality.validator import validate_dataframe
from app.storage.database import get_engine, get_session_factory, init_schema
from app.storage.repositories import (
    create_run,
    finish_run,
    insert_quarantined_records,
    upsert_orders,
)
from app.transformations.orders import transform_batch

logger = logging.getLogger("dataguard.pipeline")


def run_pipeline(input_path: str) -> dict:
    """Execute the full ETL pipeline on the given CSV file.

    Parameters
    ----------
    input_path : str
        Path to the input CSV file.

    Returns
    -------
    dict
        Summary of the run including counts and status.
    """
    config = get_config()
    setup_logging(config.log_level)

    run_id = str(uuid.uuid4())
    source_file = Path(input_path).name

    engine = get_engine(config.db.url)
    SessionFactory = get_session_factory(engine)

    # Ensure schema exists
    init_schema(engine)

    session = SessionFactory()

    try:
        # Create run record
        create_run(session, run_id, source_file)
        logger.info("Pipeline run %s started for '%s'.", run_id, source_file)

        # --- Ingestion ---
        try:
            df = read_csv(input_path)
        except IngestionError as exc:
            logger.error("Ingestion failed: %s", exc)
            finish_run(
                session,
                run_id,
                status="FAILED",
                total_records=0,
                accepted_records=0,
                rejected_records=0,
                inserted_records=0,
                updated_records=0,
                error_message=str(exc),
            )
            return {
                "run_id": run_id,
                "status": "FAILED",
                "error": str(exc),
            }

        total_records = len(df)

        # --- Validation ---
        accepted, rejected = validate_dataframe(
            df,
            allowed_statuses=config.ALLOWED_STATUSES,
            source_file=source_file,
            run_id=run_id,
        )

        # --- Transformation ---
        transformed = transform_batch(accepted)

        # --- Persistence: quarantined records ---
        insert_quarantined_records(session, rejected)

        # --- Persistence: valid orders (upsert) ---
        inserted, updated = upsert_orders(session, transformed)

        # --- Determine run status ---
        if rejected and accepted:
            status = "PARTIAL_SUCCESS"
        elif rejected and not accepted:
            status = "FAILED"
        else:
            status = "SUCCESS"

        # --- Finalize run ---
        finish_run(
            session,
            run_id,
            status=status,
            total_records=total_records,
            accepted_records=len(accepted),
            rejected_records=len(rejected),
            inserted_records=inserted,
            updated_records=updated,
        )

        summary = {
            "run_id": run_id,
            "status": status,
            "source_file": source_file,
            "total_records": total_records,
            "accepted_records": len(accepted),
            "rejected_records": len(rejected),
            "inserted_records": inserted,
            "updated_records": updated,
        }

        logger.info("Pipeline run %s completed: %s", run_id, summary)
        return summary

    except Exception as exc:
        logger.exception("Pipeline run %s failed with unexpected error.", run_id)
        try:
            finish_run(
                session,
                run_id,
                status="FAILED",
                total_records=0,
                accepted_records=0,
                rejected_records=0,
                inserted_records=0,
                updated_records=0,
                error_message=str(exc)[:500],
            )
        except Exception:
            logger.error("Could not update run status in database.")
        raise
    finally:
        session.close()


def main() -> None:
    """CLI entry point for running the DataGuard pipeline."""
    parser = argparse.ArgumentParser(
        description="DataGuard ETL Pipeline — ingest, validate, and load order data."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the input CSV file.",
    )
    args = parser.parse_args()

    try:
        summary = run_pipeline(args.input)
    except Exception:
        sys.exit(1)

    # Print summary to stdout for scripting
    print("\n" + "=" * 60)
    print("  DATAGUARD PIPELINE RUN SUMMARY")
    print("=" * 60)
    for key, value in summary.items():
        print(f"  {key:>20s}: {value}")
    print("=" * 60 + "\n")

    if summary.get("status") == "FAILED":
        sys.exit(1)


if __name__ == "__main__":
    main()
