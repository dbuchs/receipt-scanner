from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.receipt import SourceType


class LineItemBase(BaseModel):
    description_raw: str
    description_normalized: str
    sku: Optional[str] = None
    quantity: Decimal = Decimal("1")
    unit_price: Decimal = Decimal("0")
    total_price: Decimal = Decimal("0")
    discounts: Decimal = Decimal("0")
    tax_flag: bool = False
    department_hint: Optional[str] = None
    taxonomy_category_id: Optional[uuid.UUID] = None


class LineItemCreate(LineItemBase):
    pass


class LineItemUpdate(BaseModel):
    description_normalized: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    total_price: Optional[Decimal] = None
    discounts: Optional[Decimal] = None
    tax_flag: Optional[bool] = None
    department_hint: Optional[str] = None
    taxonomy_category_id: Optional[uuid.UUID] = None


class LineItemRead(LineItemBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    receipt_id: uuid.UUID


class ArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    receipt_id: uuid.UUID
    original_file_uri: str
    mime_type: str
    file_size: int


class ReceiptBase(BaseModel):
    merchant: str
    source_type: SourceType = SourceType.upload
    purchase_datetime: Optional[datetime] = None
    subtotal: Optional[Decimal] = None
    tax: Optional[Decimal] = None
    total: Optional[Decimal] = None
    currency: str = "USD"
    payment_method_last4: Optional[str] = None
    parse_confidence: float = 0.0
    parse_notes: str = ""


class ReceiptCreate(ReceiptBase):
    pass


class ReceiptUpdate(BaseModel):
    merchant: Optional[str] = None
    purchase_datetime: Optional[datetime] = None
    subtotal: Optional[Decimal] = None
    tax: Optional[Decimal] = None
    total: Optional[Decimal] = None
    currency: Optional[str] = None
    payment_method_last4: Optional[str] = None
    parse_notes: Optional[str] = None


class ReceiptRead(ReceiptBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    line_items: list[LineItemRead] = []
    artifacts: list[ArtifactRead] = []


class ReceiptListItem(ReceiptBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
