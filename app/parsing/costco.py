from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from app.parsing.base import BaseParser, CanonicalLineItem, CanonicalReceipt

# Patterns for Costco receipts
_HEADER_RE = re.compile(r"COSTCO\s+WHOLESALE", re.IGNORECASE)
_DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b")
_LAST4_RE = re.compile(
    r"(?:VISA|MC|MASTERCARD|AMEX|DISC)[^\d]*(\d{4})"
    r"|XXXX[-\s]*(\d{4})",
    re.IGNORECASE,
)

# Item line: optional SKU, description, optional qty * price, total
# Formats:
#   1234567 ITEM NAME      2  14.99   29.98
#   1234567 ITEM NAME             14.99
_ITEM_RE = re.compile(
    r"^(\d{6,8})\s+(.+?)\s+"          # SKU + description
    r"(?:(\d+)\s+)?(\d+\.\d{2})\s*"   # optional qty, unit price
    r"(?:(\d+\.\d{2}))?\s*([ETFR]?)$",  # optional total, tax flag
    re.MULTILINE,
)
_TAX_RE = re.compile(r"TAX\s+([\d,]+\.\d{2})", re.IGNORECASE)
_SUBTOTAL_RE = re.compile(r"SUBTOTAL\s+([\d,]+\.\d{2})", re.IGNORECASE)
_TOTAL_RE = re.compile(r"\bTOTAL\b\s+([\d,]+\.\d{2})", re.IGNORECASE)


def _parse_amount(s: str) -> float:
    return float(s.replace(",", ""))


class CostcoParser(BaseParser):
    merchant_name = "Costco"

    def can_parse(self, text: str) -> bool:
        return bool(_HEADER_RE.search(text))

    def parse(self, text: str, source_type: str = "upload") -> CanonicalReceipt:
        receipt = CanonicalReceipt(
            merchant=self.merchant_name,
            source_type=source_type,
            parse_confidence=0.9,
        )

        # Date
        date_m = _DATE_RE.search(text)
        if date_m:
            try:
                receipt.purchase_datetime = datetime.strptime(date_m.group(1), "%m/%d/%y")
            except ValueError:
                try:
                    receipt.purchase_datetime = datetime.strptime(date_m.group(1), "%m/%d/%Y")
                except ValueError:
                    pass

        # Last 4
        last4_m = _LAST4_RE.search(text)
        if last4_m:
            receipt.payment_method_last4 = last4_m.group(1) or last4_m.group(2)

        # Line items
        lines = text.splitlines()
        for line in lines:
            line = line.strip()
            m = _ITEM_RE.match(line)
            if m:
                sku, desc, qty_s, price1_s, price2_s, tax_code = m.groups()
                desc = desc.strip()
                if qty_s and price2_s:
                    qty = float(qty_s)
                    unit_price = _parse_amount(price1_s)
                    total_price = _parse_amount(price2_s)
                else:
                    qty = 1.0
                    unit_price = _parse_amount(price1_s)
                    total_price = unit_price
                item = CanonicalLineItem(
                    description_raw=desc,
                    description_normalized=self.normalize_description(desc),
                    sku=sku,
                    quantity=qty,
                    unit_price=unit_price,
                    total_price=total_price,
                    tax_flag=(tax_code.upper() in ("T", "E")),
                )
                receipt.line_items.append(item)

        # Totals
        sub_m = _SUBTOTAL_RE.search(text)
        if sub_m:
            receipt.subtotal = _parse_amount(sub_m.group(1))

        tax_m = _TAX_RE.search(text)
        if tax_m:
            receipt.tax = _parse_amount(tax_m.group(1))

        # Find last TOTAL match (avoid matching SUBTOTAL)
        total_matches = list(_TOTAL_RE.finditer(text))
        for tm in reversed(total_matches):
            candidate = _parse_amount(tm.group(1))
            # Skip if it looks like subtotal
            start = max(0, tm.start() - 3)
            context = text[start : tm.start()].upper()
            if "SUB" not in context:
                receipt.total = candidate
                break

        if receipt.subtotal == 0 and receipt.line_items:
            receipt.subtotal = round(
                sum(i.total_price for i in receipt.line_items), 2
            )

        notes = []
        if not receipt.line_items:
            notes.append("no line items parsed")
            receipt.parse_confidence = 0.4
        if receipt.total == 0:
            notes.append("total not found")
        receipt.parse_notes = "; ".join(notes)

        return receipt
