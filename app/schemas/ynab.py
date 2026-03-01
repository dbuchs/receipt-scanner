from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from app.models.ynab import PurposeTag, SplitStatus


class YnabTokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: str
    expires_at: Optional[datetime]
    budget_id: Optional[str]


class YnabLinkCreate(BaseModel):
    ynab_transaction_id: str
    match_score: float = 0.0
    purpose_tag: Optional[PurposeTag] = None
    return_by_date: Optional[datetime] = None
    reimburser: Optional[str] = None


class YnabLinkRead(YnabLinkCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    receipt_id: uuid.UUID
    linked_at: datetime


class YnabSplitProposalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    receipt_id: uuid.UUID
    ynab_transaction_id: str
    proposal_json: Optional[dict]
    status: SplitStatus
    created_at: datetime
    applied_at: Optional[datetime]


class MatchCandidate(BaseModel):
    transaction_id: str
    transaction_date: str
    payee_name: str
    amount_milliunits: int
    account_name: str
    score: float
    score_breakdown: dict[str, float]
    explanation: str


class SplitSubtransaction(BaseModel):
    amount: int  # milliunits
    payee_name: Optional[str] = None
    memo: Optional[str] = None
    category_id: Optional[str] = None


class SplitProposalRequest(BaseModel):
    ynab_transaction_id: str
    subtransactions: list[SplitSubtransaction]
