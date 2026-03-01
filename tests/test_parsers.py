"""Tests for receipt parsers using fixture files."""
from __future__ import annotations

import pytest

from app.parsing.aldi import AldiParser
from app.parsing.costco import CostcoParser
from app.parsing.fallback import FallbackParser
from app.parsing.pipeline import parse_receipt_text
from app.parsing.walmart import WalmartParser


class TestCostcoParser:
    def test_can_parse(self, costco_text):
        parser = CostcoParser()
        assert parser.can_parse(costco_text) is True

    def test_merchant(self, costco_text):
        parser = CostcoParser()
        receipt = parser.parse(costco_text)
        assert receipt.merchant == "Costco"

    def test_total(self, costco_text):
        parser = CostcoParser()
        receipt = parser.parse(costco_text)
        assert receipt.total == pytest.approx(110.04, abs=0.01)

    def test_tax(self, costco_text):
        parser = CostcoParser()
        receipt = parser.parse(costco_text)
        assert receipt.tax == pytest.approx(2.15, abs=0.01)

    def test_subtotal(self, costco_text):
        parser = CostcoParser()
        receipt = parser.parse(costco_text)
        assert receipt.subtotal == pytest.approx(107.89, abs=0.01)

    def test_line_items_count(self, costco_text):
        parser = CostcoParser()
        receipt = parser.parse(costco_text)
        assert len(receipt.line_items) >= 5

    def test_line_item_fields(self, costco_text):
        parser = CostcoParser()
        receipt = parser.parse(costco_text)
        for item in receipt.line_items:
            assert item.description_raw
            assert item.description_normalized
            assert item.total_price >= 0

    def test_parse_confidence(self, costco_text):
        parser = CostcoParser()
        receipt = parser.parse(costco_text)
        assert receipt.parse_confidence >= 0.8

    def test_payment_last4(self, costco_text):
        parser = CostcoParser()
        receipt = parser.parse(costco_text)
        assert receipt.payment_method_last4 == "1234"

    def test_source_type(self, costco_text):
        parser = CostcoParser()
        receipt = parser.parse(costco_text, source_type="watched_folder")
        assert receipt.source_type == "watched_folder"


class TestWalmartParser:
    def test_can_parse(self, walmart_text):
        parser = WalmartParser()
        assert parser.can_parse(walmart_text) is True

    def test_merchant(self, walmart_text):
        parser = WalmartParser()
        receipt = parser.parse(walmart_text)
        assert receipt.merchant == "Walmart"

    def test_total(self, walmart_text):
        parser = WalmartParser()
        receipt = parser.parse(walmart_text)
        assert receipt.total == pytest.approx(42.41, abs=0.01)

    def test_tax(self, walmart_text):
        parser = WalmartParser()
        receipt = parser.parse(walmart_text)
        assert receipt.tax == pytest.approx(1.04, abs=0.01)

    def test_line_items_count(self, walmart_text):
        parser = WalmartParser()
        receipt = parser.parse(walmart_text)
        assert len(receipt.line_items) >= 5

    def test_parse_confidence(self, walmart_text):
        parser = WalmartParser()
        receipt = parser.parse(walmart_text)
        assert receipt.parse_confidence >= 0.7

    def test_payment_last4(self, walmart_text):
        parser = WalmartParser()
        receipt = parser.parse(walmart_text)
        assert receipt.payment_method_last4 == "5678"


class TestAldiParser:
    def test_can_parse(self, aldi_text):
        parser = AldiParser()
        assert parser.can_parse(aldi_text) is True

    def test_merchant(self, aldi_text):
        parser = AldiParser()
        receipt = parser.parse(aldi_text)
        assert receipt.merchant == "ALDI"

    def test_total(self, aldi_text):
        parser = AldiParser()
        receipt = parser.parse(aldi_text)
        assert receipt.total == pytest.approx(23.50, abs=0.01)

    def test_tax(self, aldi_text):
        parser = AldiParser()
        receipt = parser.parse(aldi_text)
        assert receipt.tax == pytest.approx(0.48, abs=0.01)

    def test_line_items_count(self, aldi_text):
        parser = AldiParser()
        receipt = parser.parse(aldi_text)
        assert len(receipt.line_items) >= 5

    def test_parse_confidence(self, aldi_text):
        parser = AldiParser()
        receipt = parser.parse(aldi_text)
        assert receipt.parse_confidence >= 0.7

    def test_payment_last4(self, aldi_text):
        parser = AldiParser()
        receipt = parser.parse(aldi_text)
        assert receipt.payment_method_last4 == "9012"


class TestPipeline:
    def test_costco_pipeline(self, costco_text):
        receipt = parse_receipt_text(costco_text)
        assert receipt.merchant == "Costco"

    def test_walmart_pipeline(self, walmart_text):
        receipt = parse_receipt_text(walmart_text)
        assert receipt.merchant == "Walmart"

    def test_aldi_pipeline(self, aldi_text):
        receipt = parse_receipt_text(aldi_text)
        assert receipt.merchant == "ALDI"

    def test_fallback_pipeline(self):
        text = "SOME STORE\n\nWidgets     9.99\nGadgets     5.00\nTOTAL       14.99"
        receipt = parse_receipt_text(text)
        assert receipt.merchant  # Some merchant identified
        assert receipt.total == pytest.approx(14.99, abs=0.01)

    def test_costco_not_parsed_by_walmart(self, costco_text):
        parser = WalmartParser()
        assert parser.can_parse(costco_text) is False

    def test_walmart_not_parsed_by_aldi(self, walmart_text):
        parser = AldiParser()
        assert parser.can_parse(walmart_text) is False

    def test_fallback_accepts_anything(self):
        parser = FallbackParser()
        assert parser.can_parse("random text") is True


class TestBaseParserNormalize:
    def test_normalize_lowercase(self):
        from app.parsing.base import BaseParser
        assert BaseParser.normalize_description("GREAT VALUE MILK") == "great value milk"

    def test_normalize_whitespace(self):
        from app.parsing.base import BaseParser
        assert BaseParser.normalize_description("  ITEM   NAME  ") == "item name"
