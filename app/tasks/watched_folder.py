from __future__ import annotations

import uuid
from pathlib import Path

from app.config import get_settings
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.watched_folder.poll_watched_folder")
def poll_watched_folder() -> dict:
    """
    Poll the watched folder for new receipt files.
    Supported extensions: .txt, .pdf, .png, .jpg, .jpeg
    Processed files are renamed with a .done suffix to avoid re-processing.
    """
    settings = get_settings()
    folder = Path(settings.WATCHED_FOLDER_PATH)
    if not folder.exists():
        return {"processed": 0, "skipped": 0}

    extensions = {".txt", ".pdf", ".png", ".jpg", ".jpeg"}
    processed = 0
    skipped = 0

    for file_path in folder.iterdir():
        if file_path.suffix.lower() not in extensions:
            skipped += 1
            continue
        if file_path.name.endswith(".done"):
            skipped += 1
            continue

        try:
            _ingest_file(file_path)
            done_path = file_path.with_suffix(file_path.suffix + ".done")
            file_path.rename(done_path)
            processed += 1
        except Exception as exc:  # noqa: BLE001
            # Log and continue; don't crash the whole poll
            print(f"[watched_folder] Error processing {file_path}: {exc}")
            skipped += 1

    return {"processed": processed, "skipped": skipped}


def _ingest_file(file_path: Path) -> None:
    """Read file, parse receipt, persist to DB."""
    # Import here to avoid circular imports at module load
    from app.database import SessionLocal
    from app.models.receipt import Artifact, Receipt
    from app.parsing.pipeline import parse_receipt_text
    from app.services.storage import StorageService

    text = ""
    if file_path.suffix.lower() == ".txt":
        text = file_path.read_text(errors="replace")
    elif file_path.suffix.lower() == ".pdf":
        try:
            import pdfplumber

            with pdfplumber.open(str(file_path)) as pdf:
                text = "\n".join(
                    page.extract_text() or "" for page in pdf.pages
                )
        except Exception:
            text = ""

    canonical = parse_receipt_text(text, source_type="watched_folder")

    storage = StorageService()
    with open(file_path, "rb") as fobj:
        uri = storage.upload_file(
            fobj,
            filename=f"watched/{uuid.uuid4()}/{file_path.name}",
            content_type="text/plain" if file_path.suffix == ".txt" else "application/octet-stream",
        )

    db = SessionLocal()
    try:
        receipt = Receipt(
            merchant=canonical.merchant,
            source_type="watched_folder",
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
            extracted_text=text[:65535] if text else None,
            mime_type="text/plain",
            file_size=file_path.stat().st_size,
        )
        db.add(artifact)

        from app.models.receipt import LineItem

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
    finally:
        db.close()
