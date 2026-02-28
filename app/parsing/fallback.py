from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from app.parsing.base import BaseParser, CanonicalLineItem, CanonicalReceipt

_DATE_RE = re.compile(r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\b")
_PRICE_LINE_RE = re.compile(
    r"^(.{3,50?}?)\s{2,}(\d+\.\d{2})\s*$", re.MULTILINE
)
_TOTAL_RE = re.compile(r"\bTOTAL\b[:\s]+([\d,]+\.\d{2})", re.IGNORECASE)
_TAX_RE = re.compile(r"\bTAX\b[:\s]+([\d,]+\.\d{2})", re.IGNORECASE)
_SUBTOTAL_RE = re.compile(r"SUBTOTAL[:\s]+([\d,]+\.\d{2})", re.IGNORECASE)
_LAST4_RE = re.compile(r"(?:XXXX|[*]{4})[\s\-]?(\d{4})", re.IGNORECASE)
_MERCHANT_HEADER_RE = re.compile(r"^([A-Z][A-Z\s&']{2,30})\s*$", re.MULTILINE)

_SKIP_TOKENS = {
    "total", "subtotal", "tax", "change", "cash", "balance",
    "thank", "visit", "items", "savings", "cashier", "credit", "debit",
}


def _parse_amount(s: str) -> float:
    return float(s.replace(",", ""))


class FallbackParser(BaseParser):
    merchant_name = "Unknown"

    def can_parse(self, text: str) -> bool:
        # Fallback always accepts
        return True

    def parse(self, text: str, source_type: str = "upload") -> CanonicalReceipt:
        # Guess merchant from first all-caps header line
        merchant = "Unknown"
        for m in _MERCHANT_HEADER_RE.finditer(text):
            candidate = m.group(1).strip()
            if 3 <= len(candidate) <= 40:
                merchant = candidate
                break

        receipt = CanonicalReceipt(
            merchant=merchant,
            source_type=source_type,
            parse_confidence=0.3,
        )

        # Date
        date_m = _DATE_RE.search(text)
        if date_m:
            raw = date_m.group(1).replace("-", "/")
            for fmt in ("%m/%d/%y", "%m/%d/%Y"):
                try:
                    receipt.purchase_datetime = datetime.strptime(raw, fmt)
                    break
                except ValueError:
                    continue

        # Last 4
        last4_m = _LAST4_RE.search(text)
        if last4_m:
            receipt.payment_method_last4 = last4_m.group(1)

        # Line items from price-looking lines
        for m in _PRICE_LINE_RE.finditer(text):
            desc = m.group(1).strip()
            price_s = m.group(2)
            if any(t in desc.lower() for t in _SKIP_TOKENS):
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
            )
            receipt.line_items.append(item)

        sub_m = _SUBTOTAL_RE.search(text)
        if sub_m:
            receipt.subtotal = _parse_amount(sub_m.group(1))

        tax_m = _TAX_RE.search(text)
        if tax_m:
            receipt.tax = _parse_amount(tax_m.group(1))

        for tm in reversed(list(_TOTAL_RE.finditer(text))):
            context = text[max(0, tm.start() - 3) : tm.start()].upper()
            if "SUB" not in context:
                receipt.total = _parse_amount(tm.group(1))
                break

        if receipt.subtotal == 0 and receipt.line_items:
            receipt.subtotal = round(sum(i.total_price for i in receipt.line_items), 2)

        receipt.parse_notes = "fallback parser used"
        return receipt
