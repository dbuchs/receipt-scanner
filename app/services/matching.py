from __future__ import annotations

import math
import re
from datetime import datetime, date
from typing import Any

from app.parsing.base import CanonicalReceipt
from app.schemas.ynab import MatchCandidate


def _simple_similarity(a: str, b: str) -> float:
    """Character-level Jaccard similarity between two strings (lowercased)."""
    a, b = a.lower(), b.lower()
    if not a or not b:
        return 0.0
    sa = set(a.split())
    sb = set(b.split())
    if not sa and not sb:
        return 1.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def _date_score(receipt_date: datetime | None, txn_date_str: str) -> float:
    """Score 1/(1+days) for date proximity."""
    if not receipt_date:
        return 0.5  # neutral when no date
    try:
        txn_date = datetime.strptime(txn_date_str, "%Y-%m-%d").date()
    except ValueError:
        return 0.0
    days = abs((receipt_date.date() - txn_date).days)
    return 1.0 / (1.0 + days)


def _amount_score(receipt_total: float, txn_milliunits: int) -> float:
    """Score based on amount match; YNAB stores negative milliunits for outflows."""
    txn_amount = abs(txn_milliunits) / 1000.0
    if receipt_total <= 0:
        return 0.0
    diff_pct = abs(receipt_total - txn_amount) / receipt_total
    if diff_pct == 0:
        return 1.0
    if diff_pct <= 0.005:
        return 0.9
    if diff_pct <= 0.01:
        return 0.75
    if diff_pct <= 0.05:
        return 0.4
    if diff_pct <= 0.10:
        return 0.2
    return 0.0


def _last4_score(receipt_last4: str | None, txn_memo: str) -> float:
    """Bonus score if card last4 appears in transaction memo."""
    if not receipt_last4:
        return 0.0
    return 0.5 if receipt_last4 in txn_memo else 0.0


def score_transaction(receipt: CanonicalReceipt, txn: dict) -> tuple[float, dict]:
    merchant_sim = _simple_similarity(
        receipt.merchant, txn.get("payee_name", "")
    )
    date_s = _date_score(receipt.purchase_datetime, txn.get("date", ""))
    amount_s = _amount_score(receipt.total, txn.get("amount", 0))
    last4_s = _last4_score(receipt.payment_method_last4, txn.get("memo", "") or "")

    breakdown = {
        "merchant_similarity": round(merchant_sim, 3),
        "date_proximity": round(date_s, 3),
        "amount_match": round(amount_s, 3),
        "last4_bonus": round(last4_s, 3),
    }
    # Weighted combination
    score = (
        merchant_sim * 0.35
        + date_s * 0.30
        + amount_s * 0.30
        + last4_s * 0.05
    )
    return round(score, 4), breakdown


def build_explanation(breakdown: dict) -> str:
    parts = []
    if breakdown["merchant_similarity"] >= 0.5:
        parts.append("merchant name matches well")
    elif breakdown["merchant_similarity"] > 0:
        parts.append("partial merchant name match")
    else:
        parts.append("merchant name differs")

    if breakdown["date_proximity"] >= 0.9:
        parts.append("same day")
    elif breakdown["date_proximity"] >= 0.5:
        parts.append("within a few days")
    else:
        parts.append("dates are far apart")

    if breakdown["amount_match"] == 1.0:
        parts.append("exact amount match")
    elif breakdown["amount_match"] >= 0.75:
        parts.append("amount within 1%")
    elif breakdown["amount_match"] >= 0.4:
        parts.append("amount within 5%")
    elif breakdown["amount_match"] > 0:
        parts.append("amount within 10%")
    else:
        parts.append("amount does not match")

    if breakdown["last4_bonus"] > 0:
        parts.append("card last-4 confirmed")

    return "; ".join(parts)


def match_receipt_to_transactions(
    receipt: CanonicalReceipt,
    transactions: list[dict],
    top_n: int = 5,
) -> list[MatchCandidate]:
    """Return top_n best matching YNAB transactions for the given receipt."""
    scored: list[tuple[float, dict, dict]] = []
    for txn in transactions:
        score, breakdown = score_transaction(receipt, txn)
        scored.append((score, breakdown, txn))

    scored.sort(key=lambda x: x[0], reverse=True)

    results: list[MatchCandidate] = []
    for score, breakdown, txn in scored[:top_n]:
        results.append(
            MatchCandidate(
                transaction_id=txn.get("id", ""),
                transaction_date=txn.get("date", ""),
                payee_name=txn.get("payee_name", ""),
                amount_milliunits=txn.get("amount", 0),
                account_name=txn.get("account_name", ""),
                score=score,
                score_breakdown=breakdown,
                explanation=build_explanation(breakdown),
            )
        )
    return results
