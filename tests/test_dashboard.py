"""Unit tests for dashboard components and upload schema validation."""

import io
import pandas as pd

from app.ingestion.csv_reader import REQUIRED_COLUMNS


class TestDashboardUploadLogic:
    def test_required_columns_exist(self):
        expected = ["order_id", "customer_id", "order_date", "product", "quantity", "unit_price", "status"]
        assert REQUIRED_COLUMNS == expected

    def test_template_schema_compliance(self):
        template_csv = (
            "order_id,customer_id,order_date,product,quantity,unit_price,status\n"
            "ORD-101,CUST-501,2026-10-15,Widget A,5,29.99,shipped\n"
            "ORD-102,CUST-502,2026-10-16,Gadget Pro,2,99.50,pending\n"
        )
        df = pd.read_csv(io.StringIO(template_csv), dtype=str, keep_default_na=False)
        cleaned_cols = [c.strip().lower() for c in df.columns]
        missing = [c for c in REQUIRED_COLUMNS if c not in cleaned_cols]
        assert missing == []
        assert len(df) == 2

    def test_missing_column_detection(self):
        partial_csv = (
            "order_id,customer_id,order_date\n"
            "ORD-101,CUST-501,2026-10-15\n"
        )
        df = pd.read_csv(io.StringIO(partial_csv), dtype=str, keep_default_na=False)
        cleaned_cols = [c.strip().lower() for c in df.columns]
        missing = [c for c in REQUIRED_COLUMNS if c not in cleaned_cols]
        assert "product" in missing
        assert "quantity" in missing
        assert "unit_price" in missing
        assert "status" in missing
