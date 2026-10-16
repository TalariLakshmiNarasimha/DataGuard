"""Unit tests for data transformations."""

import pytest
from decimal import Decimal
from datetime import date

from app.transformations.orders import transform_record, transform_batch


class TestTransformRecord:
    """Tests for individual record transformation."""

    def _make_row(self, **overrides):
        """Return a minimal valid row dict with optional overrides."""
        row = {
            "order_id": " ORD-001 ",
            "customer_id": " CUST-101 ",
            "order_date": "2024-01-15",
            "product": " Widget A ",
            "quantity": " 5 ",
            "unit_price": " 29.99 ",
            "status": " shipped ",
            "_source_file": "test.csv",
        }
        row.update(overrides)
        return row

    def test_basic_transformation(self):
        result = transform_record(self._make_row())
        assert result["order_id"] == "ORD-001"
        assert result["customer_id"] == "CUST-101"
        assert result["order_date"] == date(2024, 1, 15)
        assert result["product"] == "Widget A"
        assert result["quantity"] == 5
        assert result["unit_price"] == Decimal("29.99")
        assert result["total_amount"] == Decimal("149.95")
        assert result["status"] == "SHIPPED"
        assert result["source_file"] == "test.csv"

    def test_whitespace_trimming(self):
        result = transform_record(self._make_row())
        assert result["order_id"] == "ORD-001"
        assert result["product"] == "Widget A"

    def test_status_normalization(self):
        result = transform_record(self._make_row(status="pending"))
        assert result["status"] == "PENDING"

    def test_total_amount_calculation(self):
        result = transform_record(self._make_row(quantity="3", unit_price="10.00"))
        assert result["total_amount"] == Decimal("30.00")

    def test_us_date_format(self):
        result = transform_record(self._make_row(order_date="01/15/2024"))
        assert result["order_date"] == date(2024, 1, 15)


class TestTransformBatch:
    """Tests for batch transformation."""

    def test_transforms_all_valid_rows(self):
        rows = [
            {
                "order_id": f"ORD-{i:03d}",
                "customer_id": f"CUST-{i}",
                "order_date": "2024-01-15",
                "product": "Widget",
                "quantity": "2",
                "unit_price": "10.00",
                "status": "shipped",
                "_source_file": "test.csv",
            }
            for i in range(5)
        ]
        result = transform_batch(rows)
        assert len(result) == 5

    def test_empty_batch(self):
        assert transform_batch([]) == []
