from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    Boolean,
    Integer,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SourceType(str, enum.Enum):
    upload = "upload"
    watched_folder = "watched_folder"
    gmail = "gmail"
    drive = "drive"


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    merchant: Mapped[str] = mapped_column(String(255), index=True)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType), default=SourceType.upload
    )
    purchase_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    subtotal: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    tax: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    total: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    payment_method_last4: Mapped[Optional[str]] = mapped_column(String(4))
    parse_confidence: Mapped[float] = mapped_column(Numeric(5, 4), default=0.0)
    parse_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    line_items: Mapped[list[LineItem]] = relationship(
        "LineItem", back_populates="receipt", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list[Artifact]] = relationship(
        "Artifact", back_populates="receipt", cascade="all, delete-orphan"
    )
    ynab_links: Mapped[list["YnabLink"]] = relationship(  # noqa: F821
        "YnabLink", back_populates="receipt", cascade="all, delete-orphan"
    )


class LineItem(Base):
    __tablename__ = "line_items"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("receipts.id", ondelete="CASCADE"), index=True
    )
    description_raw: Mapped[str] = mapped_column(Text)
    description_normalized: Mapped[str] = mapped_column(Text, index=True)
    sku: Mapped[Optional[str]] = mapped_column(String(64))
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    discounts: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    tax_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    department_hint: Mapped[Optional[str]] = mapped_column(String(128))
    taxonomy_category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("taxonomy_categories.id", ondelete="SET NULL"), nullable=True
    )

    receipt: Mapped[Receipt] = relationship("Receipt", back_populates="line_items")
    taxonomy_category: Mapped[Optional["TaxonomyCategory"]] = relationship(  # noqa: F821
        "TaxonomyCategory"
    )


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("receipts.id", ondelete="CASCADE"), index=True
    )
    original_file_uri: Mapped[str] = mapped_column(Text)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text)
    raw_source_json: Mapped[Optional[str]] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(128), default="text/plain")
    file_size: Mapped[int] = mapped_column(Integer, default=0)

    receipt: Mapped[Receipt] = relationship("Receipt", back_populates="artifacts")
