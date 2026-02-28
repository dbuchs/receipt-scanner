from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, Float, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PurposeTag(str, enum.Enum):
    reimbursement = "reimbursement"
    return_potential = "return_potential"
    history = "history"


class SplitStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    applied = "applied"
    rejected = "rejected"


class YnabToken(Base):
    __tablename__ = "ynab_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    access_token_enc: Mapped[str] = mapped_column(Text)
    refresh_token_enc: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    budget_id: Mapped[Optional[str]] = mapped_column(String(64))


class YnabLink(Base):
    __tablename__ = "ynab_links"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("receipts.id", ondelete="CASCADE"), index=True
    )
    ynab_transaction_id: Mapped[str] = mapped_column(String(64), index=True)
    match_score: Mapped[float] = mapped_column(Float, default=0.0)
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    purpose_tag: Mapped[Optional[PurposeTag]] = mapped_column(Enum(PurposeTag))
    return_by_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reimburser: Mapped[Optional[str]] = mapped_column(String(128))

    receipt: Mapped["Receipt"] = relationship("Receipt", back_populates="ynab_links")  # noqa: F821


class YnabSplitProposal(Base):
    __tablename__ = "ynab_split_proposals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("receipts.id", ondelete="CASCADE"), index=True
    )
    ynab_transaction_id: Mapped[str] = mapped_column(String(64))
    proposal_json: Mapped[Optional[dict]] = mapped_column(JSON)
    status: Mapped[SplitStatus] = mapped_column(
        Enum(SplitStatus), default=SplitStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
