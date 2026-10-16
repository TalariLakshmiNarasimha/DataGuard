"""Unit tests for data-quality validation rules.

These tests run without a database — they exercise pure validation logic.
"""

import pytest

from app.quality.rules import (
    ALL_RULES,
    check_customer_id,
    check_order_date,
    check_order_id,
    check_product,
    check_quantity,
    check_status,
    check_unit_price,
)

ALLOWED_STATUSES = ("PENDING", "SHIPPED", "DELIVERED", "CANCELLED")


# ---------------------------------------------------------------
# order_id
# ---------------------------------------------------------------

class TestCheckOrderId:
    def test_valid(self):
        assert check_order_id({"order_id": "ORD-001"}) is None

    def test_empty(self):
        assert check_order_id({"order_id": ""}) is not None

    def test_missing(self):
        assert check_order_id({}) is not None

    def test_whitespace_only(self):
        assert check_order_id({"order_id": "   "}) is not None


# ---------------------------------------------------------------
# customer_id
# ---------------------------------------------------------------

class TestCheckCustomerId:
    def test_valid(self):
        assert check_customer_id({"customer_id": "CUST-101"}) is None

    def test_empty(self):
        assert check_customer_id({"customer_id": ""}) is not None

    def test_missing(self):
        assert check_customer_id({}) is not None


# ---------------------------------------------------------------
# order_date
# ---------------------------------------------------------------

class TestCheckOrderDate:
    def test_valid_iso(self):
        assert check_order_date({"order_date": "2024-01-15"}) is None

    def test_valid_us_format(self):
        assert check_order_date({"order_date": "01/15/2024"}) is None

    def test_invalid_date(self):
        result = check_order_date({"order_date": "not-a-date"})
        assert result is not None
        assert "not a valid date" in result

    def test_empty(self):
        assert check_order_date({"order_date": ""}) is not None

    def test_missing(self):
        assert check_order_date({}) is not None


# ---------------------------------------------------------------
# product
# ---------------------------------------------------------------

class TestCheckProduct:
    def test_valid(self):
        assert check_product({"product": "Widget A"}) is None

    def test_empty(self):
        assert check_product({"product": ""}) is not None

    def test_missing(self):
        assert check_product({}) is not None


# ---------------------------------------------------------------
# quantity
# ---------------------------------------------------------------

class TestCheckQuantity:
    def test_valid(self):
        assert check_quantity({"quantity": "5"}) is None

    def test_zero(self):
        result = check_quantity({"quantity": "0"})
        assert result is not None
        assert "> 0" in result

    def test_negative(self):
        result = check_quantity({"quantity": "-3"})
        assert result is not None

    def test_non_numeric(self):
        result = check_quantity({"quantity": "abc"})
        assert result is not None
        assert "not a valid integer" in result

    def test_empty(self):
        assert check_quantity({"quantity": ""}) is not None

    def test_float_value(self):
        # "5.0" should be accepted (int-like float), "5.5" should not
        assert check_quantity({"quantity": "5.0"}) is None
        result = check_quantity({"quantity": "5.5"})
        assert result is not None


# ---------------------------------------------------------------
# unit_price
# ---------------------------------------------------------------

class TestCheckUnitPrice:
    def test_valid(self):
        assert check_unit_price({"unit_price": "29.99"}) is None

    def test_zero(self):
        assert check_unit_price({"unit_price": "0"}) is None

    def test_negative(self):
        result = check_unit_price({"unit_price": "-5.00"})
        assert result is not None
        assert ">= 0" in result

    def test_non_numeric(self):
        result = check_unit_price({"unit_price": "free"})
        assert result is not None

    def test_empty(self):
        assert check_unit_price({"unit_price": ""}) is not None


# ---------------------------------------------------------------
# status
# ---------------------------------------------------------------

class TestCheckStatus:
    def test_valid_lowercase(self):
        assert check_status({"status": "shipped"}, allowed_statuses=ALLOWED_STATUSES) is None

    def test_valid_uppercase(self):
        assert check_status({"status": "PENDING"}, allowed_statuses=ALLOWED_STATUSES) is None

    def test_invalid(self):
        result = check_status({"status": "REFUNDED"}, allowed_statuses=ALLOWED_STATUSES)
        assert result is not None
        assert "not allowed" in result

    def test_empty(self):
        result = check_status({"status": ""}, allowed_statuses=ALLOWED_STATUSES)
        assert result is not None

    def test_missing(self):
        result = check_status({}, allowed_statuses=ALLOWED_STATUSES)
        assert result is not None


# ---------------------------------------------------------------
# All rules count
# ---------------------------------------------------------------

def test_all_rules_registered():
    """Ensure all individual rules are in the ALL_RULES registry."""
    assert len(ALL_RULES) == 7


# ---------------------------------------------------------------
# Multiple rejection reasons on a single row
# ---------------------------------------------------------------

def test_multiple_rejection_reasons():
    """A row with several problems should collect all applicable reasons."""
    bad_row = {
        "order_id": "",
        "customer_id": "",
        "order_date": "bad",
        "product": "",
        "quantity": "-1",
        "unit_price": "free",
        "status": "UNKNOWN",
    }
    reasons = [
        r
        for rule in ALL_RULES
        if (r := rule(bad_row, allowed_statuses=ALLOWED_STATUSES)) is not None
    ]
    # Every field should fail
    assert len(reasons) == 7
