from __future__ import annotations

from app.parsing.base import BaseParser, CanonicalReceipt
from app.parsing.aldi import AldiParser
from app.parsing.costco import CostcoParser
from app.parsing.fallback import FallbackParser
from app.parsing.walmart import WalmartParser

_PARSERS: list[BaseParser] = [
    CostcoParser(),
    WalmartParser(),
    AldiParser(),
]
_FALLBACK = FallbackParser()


def parse_receipt_text(text: str, source_type: str = "upload") -> CanonicalReceipt:
    """Try each known parser; fall back to FallbackParser if none match."""
    for parser in _PARSERS:
        if parser.can_parse(text):
            return parser.parse(text, source_type)
    return _FALLBACK.parse(text, source_type)
