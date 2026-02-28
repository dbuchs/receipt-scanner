from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.receipt import LineItem, Receipt

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/spend-by-merchant")
def spend_by_merchant(
    db: Session = Depends(get_db),
    limit: int = Query(20, le=100),
) -> list[dict]:
    rows = (
        db.query(Receipt.merchant, func.sum(Receipt.total).label("total_spend"))
        .filter(Receipt.total.isnot(None))
        .group_by(Receipt.merchant)
        .order_by(func.sum(Receipt.total).desc())
        .limit(limit)
        .all()
    )
    return [{"merchant": r.merchant, "total_spend": float(r.total_spend)} for r in rows]


@router.get("/spend-by-category")
def spend_by_category(db: Session = Depends(get_db)) -> list[dict]:
    from app.models.rules import TaxonomyCategory

    rows = (
        db.query(
            TaxonomyCategory.name.label("category"),
            func.sum(LineItem.total_price).label("total_spend"),
        )
        .join(LineItem, LineItem.taxonomy_category_id == TaxonomyCategory.id)
        .group_by(TaxonomyCategory.name)
        .order_by(func.sum(LineItem.total_price).desc())
        .all()
    )
    return [{"category": r.category, "total_spend": float(r.total_spend)} for r in rows]


@router.get("/items/frequent")
def frequent_items(
    db: Session = Depends(get_db),
    limit: int = Query(20, le=100),
) -> list[dict]:
    rows = (
        db.query(
            LineItem.description_normalized,
            func.count(LineItem.id).label("purchase_count"),
            func.avg(LineItem.total_price).label("avg_price"),
        )
        .group_by(LineItem.description_normalized)
        .order_by(func.count(LineItem.id).desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "description": r.description_normalized,
            "purchase_count": r.purchase_count,
            "avg_price": round(float(r.avg_price), 2),
        }
        for r in rows
    ]


@router.get("/items/price-trends")
def price_trends(
    db: Session = Depends(get_db),
    description: str = Query(..., min_length=2),
) -> list[dict]:
    items = (
        db.query(LineItem, Receipt.purchase_datetime, Receipt.merchant)
        .join(Receipt, Receipt.id == LineItem.receipt_id)
        .filter(LineItem.description_normalized.ilike(f"%{description.lower()}%"))
        .order_by(Receipt.purchase_datetime)
        .all()
    )
    return [
        {
            "date": str(r.purchase_datetime.date()) if r.purchase_datetime else None,
            "merchant": r.merchant,
            "price": float(item.total_price),
        }
        for item, r in [(row[0], row) for row in items]
    ]


@router.get("/search")
def search_items(
    db: Session = Depends(get_db),
    q: str = Query(..., min_length=2),
    limit: int = Query(50, le=200),
) -> list[dict]:
    items = (
        db.query(LineItem, Receipt.merchant, Receipt.purchase_datetime)
        .join(Receipt, Receipt.id == LineItem.receipt_id)
        .filter(LineItem.description_normalized.ilike(f"%{q.lower()}%"))
        .order_by(Receipt.purchase_datetime.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "line_item_id": str(item.id),
            "receipt_id": str(item.receipt_id),
            "description": item.description_normalized,
            "total_price": float(item.total_price),
            "merchant": merchant,
            "date": str(dt.date()) if dt else None,
        }
        for item, merchant, dt in items
    ]
