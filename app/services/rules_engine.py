from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.orm import Session

from app.models.receipt import LineItem
from app.models.rules import CategoryRule, RuleType, TaxonomyCategory


def _apply_rule(rule: CategoryRule, item: LineItem) -> bool:
    """Return True if the rule matches the line item."""
    desc = item.description_normalized.lower()
    if rule.rule_type == RuleType.contains:
        if rule.pattern.lower() not in desc:
            return False
    elif rule.rule_type == RuleType.regex:
        try:
            if not re.search(rule.pattern, desc, re.IGNORECASE):
                return False
        except re.error:
            return False
    elif rule.rule_type == RuleType.merchant_dept:
        # pattern is "merchant:department" or "merchant:*"
        parts = rule.pattern.split(":", 1)
        merchant_pat = parts[0].strip().lower()
        dept_pat = parts[1].strip().lower() if len(parts) > 1 else "*"
        # merchant filter comes from the item's receipt, so we check rule fields
        if rule.merchant_filter:
            if rule.merchant_filter.lower() not in desc and rule.merchant_filter.lower() not in (
                item.department_hint or ""
            ).lower():
                return False
        if rule.department_filter and rule.department_filter != "*":
            if rule.department_filter.lower() not in (item.department_hint or "").lower():
                return False

    # Optional merchant filter check (for non-merchant_dept rules)
    if rule.rule_type != RuleType.merchant_dept and rule.merchant_filter:
        # We don't have merchant on LineItem directly; skip the filter
        pass

    return True


def apply_rules(
    db: Session,
    items: list[LineItem],
) -> list[tuple[LineItem, Optional[TaxonomyCategory], float, str]]:
    """
    Apply active CategoryRules to each LineItem.

    Returns list of (item, category, confidence, explanation) tuples.
    Items without a match get (item, None, 0.0, "no rule matched").
    """
    rules: list[CategoryRule] = (
        db.query(CategoryRule)
        .filter(CategoryRule.is_active.is_(True))
        .order_by(CategoryRule.priority.desc())
        .all()
    )

    results = []
    for item in items:
        matched_rule: Optional[CategoryRule] = None
        for rule in rules:
            if _apply_rule(rule, item):
                matched_rule = rule
                break

        if matched_rule:
            category = matched_rule.taxonomy_category
            confidence = 0.95 if matched_rule.rule_type == RuleType.contains else 0.85
            explanation = (
                f"Rule '{matched_rule.name}' matched "
                f"({matched_rule.rule_type.value}: {matched_rule.pattern!r})"
            )
            results.append((item, category, confidence, explanation))
        else:
            results.append((item, None, 0.0, "no rule matched"))

    return results


def test_rule_against_text(
    rule: CategoryRule,
    text: str,
    merchant: str = "",
    department: str = "",
) -> tuple[bool, str]:
    """Test a single rule against a text snippet. Returns (matched, explanation)."""
    fake_item = LineItem.__new__(LineItem)
    fake_item.description_normalized = BaseParser_normalize(text)  # type: ignore[attr-defined]
    fake_item.department_hint = department or None

    matched = _apply_rule(rule, fake_item)
    explanation = (
        f"Rule '{rule.name}' ({rule.rule_type.value}: {rule.pattern!r}) "
        + ("matched" if matched else "did not match")
    )
    return matched, explanation


def BaseParser_normalize(text: str) -> str:
    return " ".join(text.lower().split())
