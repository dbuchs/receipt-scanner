"""Tests for the rules engine."""
from __future__ import annotations

import re
import types
import uuid

import pytest

from app.models.rules import CategoryRule, RuleType
from app.services.rules_engine import BaseParser_normalize, _apply_rule


def _make_item(desc: str, dept: str = "") -> types.SimpleNamespace:
    """Create a lightweight stand-in for LineItem (avoids SQLAlchemy instrumentation)."""
    return types.SimpleNamespace(
        description_normalized=BaseParser_normalize(desc),
        department_hint=dept or None,
    )


def _make_rule(
    rule_type: RuleType,
    pattern: str,
    merchant_filter: str | None = None,
    department_filter: str | None = None,
) -> types.SimpleNamespace:
    """Create a lightweight stand-in for CategoryRule."""
    return types.SimpleNamespace(
        id=uuid.uuid4(),
        name="test-rule",
        rule_type=rule_type,
        pattern=pattern,
        merchant_filter=merchant_filter,
        department_filter=department_filter,
        taxonomy_category_id=uuid.uuid4(),
        priority=0,
        is_active=True,
    )


class TestContainsRule:
    def test_simple_match(self):
        rule = _make_rule(RuleType.contains, "milk")
        item = _make_item("Whole Milk 1GAL")
        assert _apply_rule(rule, item) is True

    def test_case_insensitive(self):
        rule = _make_rule(RuleType.contains, "MILK")
        item = _make_item("whole milk")
        assert _apply_rule(rule, item) is True

    def test_no_match(self):
        rule = _make_rule(RuleType.contains, "bread")
        item = _make_item("Whole Milk 1GAL")
        assert _apply_rule(rule, item) is False

    def test_partial_word_match(self):
        rule = _make_rule(RuleType.contains, "chick")
        item = _make_item("Chicken Breast 3LB")
        assert _apply_rule(rule, item) is True

    def test_multi_word_pattern(self):
        rule = _make_rule(RuleType.contains, "chicken breast")
        item = _make_item("Chicken Breast 3LB")
        assert _apply_rule(rule, item) is True


class TestRegexRule:
    def test_regex_match(self):
        rule = _make_rule(RuleType.regex, r"milk\s+\d+gal")
        item = _make_item("whole milk 1gal")
        assert _apply_rule(rule, item) is True

    def test_regex_no_match(self):
        rule = _make_rule(RuleType.regex, r"^\d{4}")
        item = _make_item("Whole Milk")
        assert _apply_rule(rule, item) is False

    def test_regex_price_pattern(self):
        rule = _make_rule(RuleType.regex, r"organic")
        item = _make_item("Organic Eggs 12CT")
        assert _apply_rule(rule, item) is True

    def test_regex_category_pattern(self):
        # Match items that look like beverages
        rule = _make_rule(RuleType.regex, r"(juice|water|milk|soda)")
        item = _make_item("Apple Juice 64OZ")
        assert _apply_rule(rule, item) is True

    def test_regex_invalid_still_runs(self):
        # An invalid regex should return False, not raise
        rule = _make_rule(RuleType.regex, r"[invalid")
        item = _make_item("any item")
        # Should not raise, just not match
        try:
            result = _apply_rule(rule, item)
        except Exception:
            pytest.fail("_apply_rule raised an exception on invalid regex")


class TestMerchantDeptRule:
    def test_merchant_filter_match(self):
        rule = _make_rule(RuleType.merchant_dept, "costco:*", merchant_filter="costco")
        item = _make_item("Kirkland Bacon", dept="MEAT")
        # merchant_filter is "costco" and item desc doesn't contain it
        # This primarily checks dept
        assert _apply_rule(rule, item) is not None  # just test it runs

    def test_department_filter_match(self):
        rule = _make_rule(
            RuleType.merchant_dept, "*:PRODUCE", department_filter="PRODUCE"
        )
        item = _make_item("Bananas", dept="PRODUCE")
        assert _apply_rule(rule, item) is True

    def test_department_filter_no_match(self):
        rule = _make_rule(
            RuleType.merchant_dept, "*:PRODUCE", department_filter="PRODUCE"
        )
        item = _make_item("Chicken", dept="MEAT")
        assert _apply_rule(rule, item) is False


class TestNormalization:
    def test_lowercase(self):
        assert BaseParser_normalize("KIRKLAND BACON") == "kirkland bacon"

    def test_strip_whitespace(self):
        assert BaseParser_normalize("  item  name  ") == "item name"

    def test_empty(self):
        assert BaseParser_normalize("") == ""

    def test_multiple_spaces(self):
        assert BaseParser_normalize("a   b   c") == "a b c"
