"""Tests for YNAB matching logic."""
from __future__ import annotations

from datetime import datetime

import pytest

from app.parsing.base import CanonicalReceipt
from app.services.matching import (
    _amount_score,
    _date_score,
    _last4_score,
    _simple_similarity,
    match_receipt_to_transactions,
    score_transaction,
)


MOCK_TRANSACTIONS = [
    {
        "id": "txn-001",
        "date": "2023-09-15",
        "payee_name": "COSTCO WHOLESALE",
        "amount": -110040,  # $110.04 in milliunits (outflow = negative)
        "account_name": "Checking",
        "memo": "VISA XXXX-1234",
    },
    {
        "id": "txn-002",
        "date": "2023-09-14",
        "payee_name": "Walmart Supercenter",
        "amount": -4241,  # $42.41
        "account_name": "Checking",
        "memo": "",
    },
    {
        "id": "txn-003",
        "date": "2023-08-01",
        "payee_name": "Amazon",
        "amount": -9999,
        "account_name": "Credit Card",
        "memo": "",
    },
]


class TestSimilarity:
    def test_exact_match(self):
        assert _simple_similarity("costco", "costco") == pytest.approx(1.0)

    def test_partial_match(self):
        score = _simple_similarity("COSTCO WHOLESALE", "Costco")
        assert 0 < score < 1.0

    def test_no_match(self):
        score = _simple_similarity("Walmart", "Amazon")
        assert score == pytest.approx(0.0)

    def test_empty_strings(self):
        assert _simple_similarity("", "walmart") == pytest.approx(0.0)


class TestDateScore:
    def test_same_day(self):
        dt = datetime(2023, 9, 15)
        score = _date_score(dt, "2023-09-15")
        assert score == pytest.approx(1.0)

    def test_one_day_off(self):
        dt = datetime(2023, 9, 15)
        score = _date_score(dt, "2023-09-14")
        assert score == pytest.approx(0.5)

    def test_far_away(self):
        dt = datetime(2023, 9, 15)
        score = _date_score(dt, "2022-01-01")
        assert score < 0.01

    def test_no_receipt_date(self):
        score = _date_score(None, "2023-09-15")
        assert score == pytest.approx(0.5)

    def test_invalid_txn_date(self):
        dt = datetime(2023, 9, 15)
        score = _date_score(dt, "not-a-date")
        assert score == pytest.approx(0.0)


class TestAmountScore:
    def test_exact_match(self):
        assert _amount_score(110.04, -110040) == pytest.approx(1.0)

    def test_within_half_percent(self):
        score = _amount_score(100.00, -99500)  # 0.5% off
        assert score >= 0.9

    def test_within_one_percent(self):
        score = _amount_score(100.00, -99000)  # 1% off
        assert score >= 0.5

    def test_large_discrepancy(self):
        score = _amount_score(100.00, -50000)  # 50% off
        assert score == pytest.approx(0.0)

    def test_zero_receipt_total(self):
        assert _amount_score(0.0, -110040) == pytest.approx(0.0)


class TestLast4Score:
    def test_match_in_memo(self):
        score = _last4_score("1234", "VISA XXXX-1234")
        assert score > 0.0

    def test_no_match(self):
        score = _last4_score("9999", "VISA XXXX-1234")
        assert score == pytest.approx(0.0)

    def test_none_last4(self):
        score = _last4_score(None, "VISA XXXX-1234")
        assert score == pytest.approx(0.0)


class TestScoreTransaction:
    def test_high_score_for_exact_match(self):
        receipt = CanonicalReceipt(
            merchant="Costco Wholesale",
            source_type="upload",
            purchase_datetime=datetime(2023, 9, 15),
            total=110.04,
            payment_method_last4="1234",
        )
        score, breakdown = score_transaction(receipt, MOCK_TRANSACTIONS[0])
        assert score >= 0.7
        assert "merchant_similarity" in breakdown
        assert "date_proximity" in breakdown
        assert "amount_match" in breakdown

    def test_low_score_for_wrong_merchant(self):
        receipt = CanonicalReceipt(
            merchant="Costco Wholesale",
            source_type="upload",
            purchase_datetime=datetime(2023, 9, 15),
            total=110.04,
        )
        score, _ = score_transaction(receipt, MOCK_TRANSACTIONS[2])
        assert score < 0.5


class TestMatchReceiptToTransactions:
    def test_returns_top_5(self):
        receipt = CanonicalReceipt(
            merchant="Costco",
            source_type="upload",
            purchase_datetime=datetime(2023, 9, 15),
            total=110.04,
        )
        results = match_receipt_to_transactions(receipt, MOCK_TRANSACTIONS, top_n=5)
        assert len(results) <= 5
        assert len(results) == len(MOCK_TRANSACTIONS)

    def test_sorted_by_score(self):
        receipt = CanonicalReceipt(
            merchant="Costco Wholesale",
            source_type="upload",
            purchase_datetime=datetime(2023, 9, 15),
            total=110.04,
        )
        results = match_receipt_to_transactions(receipt, MOCK_TRANSACTIONS)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_best_match_is_costco(self):
        receipt = CanonicalReceipt(
            merchant="Costco Wholesale",
            source_type="upload",
            purchase_datetime=datetime(2023, 9, 15),
            total=110.04,
            payment_method_last4="1234",
        )
        results = match_receipt_to_transactions(receipt, MOCK_TRANSACTIONS)
        assert results[0].transaction_id == "txn-001"

    def test_empty_transactions(self):
        receipt = CanonicalReceipt(merchant="Costco", source_type="upload")
        results = match_receipt_to_transactions(receipt, [])
        assert results == []

    def test_candidate_has_explanation(self):
        receipt = CanonicalReceipt(
            merchant="Costco",
            source_type="upload",
            purchase_datetime=datetime(2023, 9, 15),
            total=110.04,
        )
        results = match_receipt_to_transactions(receipt, MOCK_TRANSACTIONS)
        for r in results:
            assert r.explanation
            assert r.payee_name
