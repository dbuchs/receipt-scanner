from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.audit import AuditLog
from app.models.receipt import Receipt
from app.models.ynab import SplitStatus, YnabLink, YnabSplitProposal, YnabToken
from app.schemas.ynab import (
    MatchCandidate,
    SplitProposalRequest,
    YnabLinkCreate,
    YnabLinkRead,
    YnabSplitProposalRead,
)
from app.services.crypto import decrypt, encrypt
from app.services.matching import match_receipt_to_transactions
from app.services.ynab_client import YnabClient

router = APIRouter(prefix="/ynab", tags=["ynab"])

_STATE_STORE: dict[str, str] = {}  # In-memory; replace with Redis in production


def _get_token(db: Session, user_id: str = "default") -> YnabToken:
    token_row = db.query(YnabToken).filter(YnabToken.user_id == user_id).first()
    if not token_row:
        raise HTTPException(status_code=401, detail="YNAB not connected")
    return token_row


def _make_client(token_row: YnabToken) -> YnabClient:
    access_token = decrypt(token_row.access_token_enc)
    return YnabClient(access_token)


@router.get("/connect")
def ynab_connect(request: Request) -> RedirectResponse:
    state = secrets.token_urlsafe(16)
    _STATE_STORE[state] = "pending"
    url = YnabClient.get_authorize_url(state)
    return RedirectResponse(url)


@router.get("/callback")
async def ynab_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
) -> dict:
    if state not in _STATE_STORE:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    _STATE_STORE.pop(state)

    token_data = await YnabClient.exchange_code(code)
    expires_at = None
    if "expires_in" in token_data:
        from datetime import timedelta

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_data["expires_in"])

    existing = db.query(YnabToken).filter(YnabToken.user_id == "default").first()
    if existing:
        existing.access_token_enc = encrypt(token_data["access_token"])
        existing.refresh_token_enc = encrypt(token_data.get("refresh_token", ""))
        existing.expires_at = expires_at
    else:
        db.add(
            YnabToken(
                user_id="default",
                access_token_enc=encrypt(token_data["access_token"]),
                refresh_token_enc=encrypt(token_data.get("refresh_token", "")),
                expires_at=expires_at,
            )
        )
    db.commit()
    return {"status": "connected"}


@router.get("/budgets")
async def list_budgets(db: Session = Depends(get_db)) -> list[dict]:
    token_row = _get_token(db)
    client = _make_client(token_row)
    return await client.get_budgets()


@router.get("/match/{receipt_id}", response_model=list[MatchCandidate])
async def get_match_candidates(
    receipt_id: uuid.UUID,
    since_date: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> list[MatchCandidate]:
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    token_row = _get_token(db)
    client = _make_client(token_row)

    budget_id = token_row.budget_id
    if not budget_id:
        raise HTTPException(status_code=400, detail="No default budget set on YNAB token")

    transactions = await client.get_transactions(budget_id, since_date=since_date)

    from app.parsing.base import CanonicalReceipt

    canonical = CanonicalReceipt(
        merchant=receipt.merchant,
        source_type=str(receipt.source_type),
        purchase_datetime=receipt.purchase_datetime,
        total=float(receipt.total or 0),
        payment_method_last4=receipt.payment_method_last4,
    )
    return match_receipt_to_transactions(canonical, transactions)


@router.post("/match/{receipt_id}", response_model=YnabLinkRead)
def confirm_match(
    receipt_id: uuid.UUID,
    payload: YnabLinkCreate,
    db: Session = Depends(get_db),
) -> YnabLinkRead:
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    link = YnabLink(
        receipt_id=receipt_id,
        ynab_transaction_id=payload.ynab_transaction_id,
        match_score=payload.match_score,
        purpose_tag=payload.purpose_tag,
        return_by_date=payload.return_by_date,
        reimburser=payload.reimburser,
    )
    db.add(link)

    db.add(
        AuditLog(
            action="match_confirmed",
            entity_type="YnabLink",
            entity_id=str(receipt_id),
            after_json=payload.model_dump_json(),
        )
    )
    db.commit()
    db.refresh(link)
    return YnabLinkRead.model_validate(link)


@router.get("/split/{receipt_id}", response_model=YnabSplitProposalRead)
def get_split_proposal(
    receipt_id: uuid.UUID,
    ynab_transaction_id: str = Query(...),
    db: Session = Depends(get_db),
) -> YnabSplitProposalRead:
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    existing = (
        db.query(YnabSplitProposal)
        .filter(
            YnabSplitProposal.receipt_id == receipt_id,
            YnabSplitProposal.ynab_transaction_id == ynab_transaction_id,
            YnabSplitProposal.status == SplitStatus.pending,
        )
        .first()
    )
    if existing:
        return YnabSplitProposalRead.model_validate(existing)

    # Build proposal from line items
    subtransactions = []
    for item in receipt.line_items:
        amount_milliunits = -int(float(item.total_price) * 1000)
        subtransactions.append(
            {
                "amount": amount_milliunits,
                "memo": item.description_normalized,
                "category_id": (
                    str(item.taxonomy_category.ynab_category_id)
                    if item.taxonomy_category and item.taxonomy_category.ynab_category_id
                    else None
                ),
            }
        )

    proposal = YnabSplitProposal(
        receipt_id=receipt_id,
        ynab_transaction_id=ynab_transaction_id,
        proposal_json={"subtransactions": subtransactions},
        status=SplitStatus.pending,
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    return YnabSplitProposalRead.model_validate(proposal)


@router.post("/split/{receipt_id}/confirm")
async def confirm_split(
    receipt_id: uuid.UUID,
    payload: SplitProposalRequest,
    db: Session = Depends(get_db),
) -> dict:
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    token_row = _get_token(db)
    client = _make_client(token_row)
    budget_id = token_row.budget_id
    if not budget_id:
        raise HTTPException(status_code=400, detail="No default budget set")

    subtransactions = [s.model_dump() for s in payload.subtransactions]
    txn_data = {"subtransactions": subtransactions}

    updated = await client.update_transaction(
        budget_id, payload.ynab_transaction_id, txn_data
    )

    # Mark proposal as applied
    proposal = (
        db.query(YnabSplitProposal)
        .filter(
            YnabSplitProposal.receipt_id == receipt_id,
            YnabSplitProposal.ynab_transaction_id == payload.ynab_transaction_id,
        )
        .first()
    )
    if proposal:
        proposal.status = SplitStatus.applied
        proposal.applied_at = datetime.now(timezone.utc)

    db.add(
        AuditLog(
            action="split_applied",
            entity_type="YnabSplitProposal",
            entity_id=str(receipt_id),
            after_json=str(subtransactions),
        )
    )
    db.commit()
    return {"status": "applied", "transaction_id": payload.ynab_transaction_id}
