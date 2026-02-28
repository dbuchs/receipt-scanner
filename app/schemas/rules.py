from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.rules import RuleType


class TaxonomyCategoryBase(BaseModel):
    name: str
    parent_id: Optional[uuid.UUID] = None
    ynab_category_id: Optional[str] = None
    description: Optional[str] = None


class TaxonomyCategoryCreate(TaxonomyCategoryBase):
    pass


class TaxonomyCategoryUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    ynab_category_id: Optional[str] = None
    description: Optional[str] = None


class TaxonomyCategoryRead(TaxonomyCategoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class CategoryRuleBase(BaseModel):
    name: str
    rule_type: RuleType
    pattern: str
    merchant_filter: Optional[str] = None
    department_filter: Optional[str] = None
    taxonomy_category_id: uuid.UUID
    priority: int = 0
    is_active: bool = True


class CategoryRuleCreate(CategoryRuleBase):
    pass


class CategoryRuleUpdate(BaseModel):
    name: Optional[str] = None
    rule_type: Optional[RuleType] = None
    pattern: Optional[str] = None
    merchant_filter: Optional[str] = None
    department_filter: Optional[str] = None
    taxonomy_category_id: Optional[uuid.UUID] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class CategoryRuleRead(CategoryRuleBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class RuleTestRequest(BaseModel):
    text: str
    merchant: Optional[str] = None
    department: Optional[str] = None


class RuleTestResult(BaseModel):
    matched: bool
    rule_id: Optional[uuid.UUID] = None
    rule_name: Optional[str] = None
    taxonomy_category_id: Optional[uuid.UUID] = None
    confidence: float = 0.0
    explanation: str = ""
