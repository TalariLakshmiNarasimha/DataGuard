"""Tests for pipeline-level logic: ingestion, validation flow, and edge cases.

These tests exercise the validator, CSV reader, and end-to-end flows
without requiring a live PostgreSQL database.
"""

import os
import tempfile

import pandas as pd
import pytest

from app.ingestion.csv_reader import IngestionError, read_csv
from app.quality.validator import validate_dataframe

ALLOWED_STATUSES = ("PENDING", "SHIPPED", "DELIVERED", "CANCELLED")

VALID_CSV = """\
order_id,customer_id,order_date,product,quantity,unit_price,status
ORD-001,CUST-101,2024-01-15,Widget A,5,29.99,shipped
ORD-002,CUST-102,2024-01-16,Widget B,3,49.99,pending
"""

MISSING_COLUMNS_CSV = """\
order_id,customer_id,order_date,product
ORD-001,CUST-101,2024-01-15,Widget A
"""

HEADER_ONLY_CSV = """\
order_id,customer_id,order_date,product,quantity,unit_price,status
"""

DUPLICATE_IDS_CSV = """\
order_id,customer_id,order_date,product,quantity,unit_price,status
ORD-001,CUST-101,2024-01-15,Widget A,5,29.99,shipped
ORD-001,CUST-102,2024-01-16,Widget B,3,49.99,pending
"""

MIXED_QUALITY_CSV = """\
order_id,customer_id,order_date,product,quantity,unit_price,status
ORD-001,CUST-101,2024-01-15,Widget A,5,29.99,shipped
ORD-002,,invalid-date,,0,-5,REFUNDED
"""


def _write_temp_csv(content: str) -> str:
    """Write content to a temporary file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.write(fd, content.encode("utf-8"))
    os.close(fd)
    return path


# ---------------------------------------------------------------
# CSV Ingestion Tests
# ---------------------------------------------------------------

class TestCSVReader:
    def test_read_valid_csv(self):
        path = _write_temp_csv(VALID_CSV)
        try:
            df = read_csv(path)
            assert len(df) == 2
            assert "_source_row_number" in df.columns
            assert df["_source_row_number"].iloc[0] == 1
        finally:
            os.unlink(path)

    def test_missing_file(self):
        with pytest.raises(IngestionError, match="not found"):
            read_csv("/nonexistent/path/to/file.csv")

    def test_empty_file(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            with pytest.raises(IngestionError, match="empty"):
                read_csv(path)
        finally:
            os.unlink(path)

    def test_missing_columns(self):
        path = _write_temp_csv(MISSING_COLUMNS_CSV)
        try:
            with pytest.raises(IngestionError, match="missing required columns"):
                read_csv(path)
        finally:
            os.unlink(path)

    def test_header_only(self):
        path = _write_temp_csv(HEADER_ONLY_CSV)
        try:
            with pytest.raises(IngestionError, match="no data rows"):
                read_csv(path)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------
# Validation Flow Tests
# ---------------------------------------------------------------

class TestValidateDataframe:
    def test_all_valid(self):
        path = _write_temp_csv(VALID_CSV)
        try:
            df = read_csv(path)
            accepted, rejected = validate_dataframe(
                df, ALLOWED_STATUSES, "test.csv", "run-1"
            )
            assert len(accepted) == 2
            assert len(rejected) == 0
        finally:
            os.unlink(path)

    def test_duplicate_ids(self):
        path = _write_temp_csv(DUPLICATE_IDS_CSV)
        try:
            df = read_csv(path)
            accepted, rejected = validate_dataframe(
                df, ALLOWED_STATUSES, "test.csv", "run-1"
            )
            assert len(accepted) == 1
            assert len(rejected) == 1
            assert "Duplicate" in rejected[0]["rejection_reasons"]
        finally:
            os.unlink(path)

    def test_mixed_quality(self):
        path = _write_temp_csv(MIXED_QUALITY_CSV)
        try:
            df = read_csv(path)
            accepted, rejected = validate_dataframe(
                df, ALLOWED_STATUSES, "test.csv", "run-1"
            )
            assert len(accepted) == 1
            assert len(rejected) == 1
            # The bad row should have multiple rejection reasons
            import json
            reasons = json.loads(rejected[0]["rejection_reasons"])
            assert len(reasons) >= 5  # customer_id, date, product, quantity, price, status
        finally:
            os.unlink(path)

    def test_rejected_record_metadata(self):
        path = _write_temp_csv(MIXED_QUALITY_CSV)
        try:
            df = read_csv(path)
            _, rejected = validate_dataframe(
                df, ALLOWED_STATUSES, "test.csv", "run-42"
            )
            rec = rejected[0]
            assert rec["run_id"] == "run-42"
            assert rec["source_file"] == "test.csv"
            assert rec["source_row_number"] == 2
            assert "raw_record" in rec
            assert "rejection_reasons" in rec
        finally:
            os.unlink(path)
