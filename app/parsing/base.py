from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class CanonicalLineItem:
    description_raw: str
    description_normalized: str
    quantity: float = 1.0
    unit_price: float = 0.0
    total_price: float = 0.0
    discounts: float = 0.0
    sku: Optional[str] = None
    tax_flag: bool = False
    department_hint: Optional[str] = None


@dataclass
class CanonicalReceipt:
    merchant: str
    source_type: str
    line_items: list = field(default_factory=list)
    purchase_datetime: Optional[datetime] = None
    subtotal: float = 0.0
    tax: float = 0.0
    total: float = 0.0
    currency: str = "USD"
    payment_method_last4: Optional[str] = None
    parse_confidence: float = 0.0
    parse_notes: str = ""


class BaseParser:
    merchant_name: str = "Unknown"

    def can_parse(self, text: str) -> bool:
        raise NotImplementedError

    def parse(self, text: str, source_type: str = "upload") -> CanonicalReceipt:
        raise NotImplementedError

    @staticmethod
    def normalize_description(desc: str) -> str:
        return " ".join(desc.lower().split())
