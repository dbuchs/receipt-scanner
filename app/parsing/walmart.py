from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from app.parsing.base import BaseParser, CanonicalLineItem, CanonicalReceipt

_HEADER_RE = re.compile(r"WAL[\*\-\s]*MART|Walmart", re.IGNORECASE)
_DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b")
_LAST4_RE = re.compile(r"(?:VISA|MC|MASTERCARD|DEBIT|CREDIT)[^\d]*\*+(\d{4})", re.IGNORECASE)
_LAST4_RE2 = re.compile(r"XXXX[\-\s]*(\d{4})", re.IGNORECASE)

# Walmart item: description optionally followed by dept code, then price
# e.g.: "GREAT VALUE MILK        F   2.98"
# or:   "BANANAS                     0.63"
_ITEM_RE = re.compile(
    r"^(.+?)\s{2,}"                # description (lazy, stops at 2+ spaces)
    r"([A-Z0-9]{0,3})\s*"          # optional dept/tax code
    r"(\d+\.\d{2})\s*[A-Z]?$",     # price
    re.MULTILINE,
)
_SUBTOTAL_RE = re.compile(r"SUBTOTAL\s+([\d,]+\.\d{2})", re.IGNORECASE)
_TAX_RE = re.compile(r"TAX\s*[12]?\s+([\d,]+\.\d{2})", re.IGNORECASE)
_TOTAL_RE = re.compile(r"\bTOTAL\b\s+([\d,]+\.\d{2})", re.IGNORECASE)

_SKIP_LINES = re.compile(
    r"^(SUBTOTAL|TAX|TOTAL|CHANGE|CASH|CREDIT|DEBIT|VISA|MASTERCARD|THANK|SAVINGS|BALANCE|ITEMS\s+SOLD)",
    re.IGNORECASE,
)


def _parse_amount(s: str) -> float:
    return float(s.replace(",", ""))


class WalmartParser(BaseParser):
    merchant_name = "Walmart"

    def can_parse(self, text: str) -> bool:
        return bool(_HEADER_RE.search(text))

    def parse(self, text: str, source_type: str = "upload") -> CanonicalReceipt:
        receipt = CanonicalReceipt(
            merchant=self.merchant_name,
            source_type=source_type,
            parse_confidence=0.85,
        )

        # Date
        date_m = _DATE_RE.search(text)
        if date_m:
            for fmt in ("%m/%d/%y", "%m/%d/%Y"):
                try:
                    receipt.purchase_datetime = datetime.strptime(date_m.group(1), fmt)
                    break
                except ValueError:
                    continue

        # Last 4
        for pat in (_LAST4_RE, _LAST4_RE2):
            m = pat.search(text)
            if m:
                receipt.payment_method_last4 = m.group(1)
                break

        # Line items
        for m in _ITEM_RE.finditer(text):
            desc, dept, price_s = m.group(1).strip(), m.group(2).strip(), m.group(3)
            if _SKIP_LINES.match(desc):
                continue
            if len(desc) < 3:
                continue
            price = _parse_amount(price_s)
            item = CanonicalLineItem(
                description_raw=desc,
                description_normalized=self.normalize_description(desc),
                quantity=1.0,
                unit_price=price,
                total_price=price,
                department_hint=dept or None,
                tax_flag=(dept.upper() in ("T", "TX", "1", "2")),
            )
            receipt.line_items.append(item)

        sub_m = _SUBTOTAL_RE.search(text)
        if sub_m:
            receipt.subtotal = _parse_amount(sub_m.group(1))

        tax_m = _TAX_RE.search(text)
        if tax_m:
            receipt.tax = _parse_amount(tax_m.group(1))

        total_matches = list(_TOTAL_RE.finditer(text))
        for tm in reversed(total_matches):
            context = text[max(0, tm.start() - 3) : tm.start()].upper()
            if "SUB" not in context:
                receipt.total = _parse_amount(tm.group(1))
                break

        if receipt.subtotal == 0 and receipt.line_items:
            receipt.subtotal = round(sum(i.total_price for i in receipt.line_items), 2)

        notes = []
        if not receipt.line_items:
            notes.append("no line items parsed")
            receipt.parse_confidence = 0.4
        if receipt.total == 0:
            notes.append("total not found")
        receipt.parse_notes = "; ".join(notes)
        return receipt
