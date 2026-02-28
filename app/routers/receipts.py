from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.receipt import LineItem, Receipt
from app.schemas.receipt import LineItemRead, LineItemUpdate, ReceiptListItem, ReceiptRead, ReceiptUpdate

router = APIRouter(prefix="/receipts", tags=["receipts"])


@router.get("", response_model=list[ReceiptListItem])
def list_receipts(
    db: Session = Depends(get_db),
    merchant: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = 0,
) -> list[ReceiptListItem]:
    q = db.query(Receipt).order_by(Receipt.created_at.desc())
    if merchant:
        q = q.filter(Receipt.merchant.ilike(f"%{merchant}%"))
    return [ReceiptListItem.model_validate(r) for r in q.offset(offset).limit(limit).all()]


@router.get("/{receipt_id}", response_model=ReceiptRead)
def get_receipt(receipt_id: uuid.UUID, db: Session = Depends(get_db)) -> ReceiptRead:
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return ReceiptRead.model_validate(receipt)


@router.patch("/{receipt_id}", response_model=ReceiptRead)
def update_receipt(
    receipt_id: uuid.UUID,
    payload: ReceiptUpdate,
    db: Session = Depends(get_db),
) -> ReceiptRead:
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(receipt, field, value)
    db.commit()
    db.refresh(receipt)
    return ReceiptRead.model_validate(receipt)


@router.get("/{receipt_id}/items", response_model=list[LineItemRead])
def get_line_items(
    receipt_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[LineItemRead]:
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return [LineItemRead.model_validate(li) for li in receipt.line_items]


@router.patch("/{receipt_id}/items/{item_id}", response_model=LineItemRead)
def update_line_item(
    receipt_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: LineItemUpdate,
    db: Session = Depends(get_db),
) -> LineItemRead:
    item = db.get(LineItem, item_id)
    if not item or item.receipt_id != receipt_id:
        raise HTTPException(status_code=404, detail="Line item not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return LineItemRead.model_validate(item)
