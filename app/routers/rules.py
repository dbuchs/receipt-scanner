from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.rules import CategoryRule, TaxonomyCategory
from app.schemas.rules import (
    CategoryRuleCreate,
    CategoryRuleRead,
    CategoryRuleUpdate,
    RuleTestRequest,
    RuleTestResult,
    TaxonomyCategoryCreate,
    TaxonomyCategoryRead,
    TaxonomyCategoryUpdate,
)
from app.services.rules_engine import BaseParser_normalize, _apply_rule

router = APIRouter(tags=["rules"])


# ── Taxonomy ───────────────────────────────────────────────────────────────────

@router.get("/taxonomy", response_model=list[TaxonomyCategoryRead])
def list_taxonomy(db: Session = Depends(get_db)) -> list[TaxonomyCategoryRead]:
    cats = db.query(TaxonomyCategory).order_by(TaxonomyCategory.name).all()
    return [TaxonomyCategoryRead.model_validate(c) for c in cats]


@router.post("/taxonomy", response_model=TaxonomyCategoryRead, status_code=201)
def create_taxonomy(
    payload: TaxonomyCategoryCreate, db: Session = Depends(get_db)
) -> TaxonomyCategoryRead:
    cat = TaxonomyCategory(**payload.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return TaxonomyCategoryRead.model_validate(cat)


@router.patch("/taxonomy/{cat_id}", response_model=TaxonomyCategoryRead)
def update_taxonomy(
    cat_id: uuid.UUID,
    payload: TaxonomyCategoryUpdate,
    db: Session = Depends(get_db),
) -> TaxonomyCategoryRead:
    cat = db.get(TaxonomyCategory, cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Taxonomy category not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return TaxonomyCategoryRead.model_validate(cat)


@router.delete("/taxonomy/{cat_id}", status_code=204)
def delete_taxonomy(cat_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    cat = db.get(TaxonomyCategory, cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Taxonomy category not found")
    db.delete(cat)
    db.commit()


# ── Rules ──────────────────────────────────────────────────────────────────────

@router.get("/rules", response_model=list[CategoryRuleRead])
def list_rules(db: Session = Depends(get_db)) -> list[CategoryRuleRead]:
    rules = (
        db.query(CategoryRule)
        .order_by(CategoryRule.priority.desc(), CategoryRule.name)
        .all()
    )
    return [CategoryRuleRead.model_validate(r) for r in rules]


@router.post("/rules", response_model=CategoryRuleRead, status_code=201)
def create_rule(
    payload: CategoryRuleCreate, db: Session = Depends(get_db)
) -> CategoryRuleRead:
    rule = CategoryRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return CategoryRuleRead.model_validate(rule)


@router.patch("/rules/{rule_id}", response_model=CategoryRuleRead)
def update_rule(
    rule_id: uuid.UUID,
    payload: CategoryRuleUpdate,
    db: Session = Depends(get_db),
) -> CategoryRuleRead:
    rule = db.get(CategoryRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
    db.commit()
    db.refresh(rule)
    return CategoryRuleRead.model_validate(rule)


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    rule = db.get(CategoryRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()


@router.post("/rules/test", response_model=RuleTestResult)
def test_rule(
    payload: RuleTestRequest, db: Session = Depends(get_db)
) -> RuleTestResult:
    """Test all active rules against a text sample. Returns the first match."""
    rules = (
        db.query(CategoryRule)
        .filter(CategoryRule.is_active.is_(True))
        .order_by(CategoryRule.priority.desc())
        .all()
    )

    from app.models.receipt import LineItem

    fake_item = LineItem.__new__(LineItem)
    fake_item.description_normalized = BaseParser_normalize(payload.text)
    fake_item.department_hint = payload.department or None

    for rule in rules:
        if _apply_rule(rule, fake_item):
            return RuleTestResult(
                matched=True,
                rule_id=rule.id,
                rule_name=rule.name,
                taxonomy_category_id=rule.taxonomy_category_id,
                confidence=0.95,
                explanation=f"Rule '{rule.name}' matched pattern '{rule.pattern}'",
            )
    return RuleTestResult(matched=False, explanation="No active rule matched")
