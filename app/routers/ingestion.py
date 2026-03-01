from __future__ import annotations

import io
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.receipt import Artifact, LineItem, Receipt, SourceType
from app.parsing.pipeline import parse_receipt_text
from app.schemas.receipt import ReceiptListItem
from app.services.storage import StorageService

router = APIRouter(tags=["ingestion"])


@router.post("/upload", status_code=201)
async def upload_receipts(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Accept one or more receipt files, parse, store, and return receipt IDs."""
    storage = StorageService()
    created = []

    for upload in files:
        raw = await upload.read()
        mime = upload.content_type or "application/octet-stream"

        # Extract text
        if mime == "application/pdf" or (upload.filename or "").endswith(".pdf"):
            try:
                import pdfplumber

                with pdfplumber.open(io.BytesIO(raw)) as pdf:
                    text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            except Exception:
                text = raw.decode("utf-8", errors="replace")
        else:
            text = raw.decode("utf-8", errors="replace")

        canonical = parse_receipt_text(text, source_type="upload")

        # Persist to MinIO
        uri = storage.upload_file(
            io.BytesIO(raw),
            filename=f"uploads/{uuid.uuid4()}/{upload.filename or 'receipt'}",
            content_type=mime,
        )

        receipt = Receipt(
            merchant=canonical.merchant,
            source_type=SourceType.upload,
            purchase_datetime=canonical.purchase_datetime,
            subtotal=canonical.subtotal or None,
            tax=canonical.tax or None,
            total=canonical.total or None,
            currency=canonical.currency,
            payment_method_last4=canonical.payment_method_last4,
            parse_confidence=canonical.parse_confidence,
            parse_notes=canonical.parse_notes,
        )
        db.add(receipt)
        db.flush()

        artifact = Artifact(
            receipt_id=receipt.id,
            original_file_uri=uri,
            extracted_text=text[:65535],
            mime_type=mime,
            file_size=len(raw),
        )
        db.add(artifact)

        for ci in canonical.line_items:
            li = LineItem(
                receipt_id=receipt.id,
                description_raw=ci.description_raw,
                description_normalized=ci.description_normalized,
                sku=ci.sku,
                quantity=ci.quantity,
                unit_price=ci.unit_price,
                total_price=ci.total_price,
                discounts=ci.discounts,
                tax_flag=ci.tax_flag,
                department_hint=ci.department_hint,
            )
            db.add(li)

        db.commit()
        db.refresh(receipt)
        created.append({"receipt_id": str(receipt.id), "merchant": receipt.merchant})

    return created


@router.get("/inbox")
def get_inbox(
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
) -> list[ReceiptListItem]:
    """List receipts that have no YNAB link (unmatched inbox)."""
    from app.models.ynab import YnabLink

    linked_ids = db.query(YnabLink.receipt_id).subquery()
    receipts = (
        db.query(Receipt)
        .filter(Receipt.id.notin_(linked_ids))
        .order_by(Receipt.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [ReceiptListItem.model_validate(r) for r in receipts]
