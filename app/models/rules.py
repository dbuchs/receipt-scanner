from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RuleType(str, enum.Enum):
    contains = "contains"
    regex = "regex"
    merchant_dept = "merchant_dept"


class TaxonomyCategory(Base):
    __tablename__ = "taxonomy_categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), index=True)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("taxonomy_categories.id", ondelete="SET NULL"), nullable=True
    )
    ynab_category_id: Mapped[Optional[str]] = mapped_column(String(64))
    description: Mapped[Optional[str]] = mapped_column(Text)

    parent: Mapped[Optional[TaxonomyCategory]] = relationship(
        "TaxonomyCategory", remote_side="TaxonomyCategory.id"
    )
    children: Mapped[list[TaxonomyCategory]] = relationship(
        "TaxonomyCategory", back_populates="parent"
    )
    rules: Mapped[list[CategoryRule]] = relationship(
        "CategoryRule", back_populates="taxonomy_category"
    )


class CategoryRule(Base):
    __tablename__ = "category_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128))
    rule_type: Mapped[RuleType] = mapped_column(Enum(RuleType))
    pattern: Mapped[str] = mapped_column(Text)
    merchant_filter: Mapped[Optional[str]] = mapped_column(String(255))
    department_filter: Mapped[Optional[str]] = mapped_column(String(128))
    taxonomy_category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy_categories.id", ondelete="CASCADE")
    )
    priority: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    taxonomy_category: Mapped[TaxonomyCategory] = relationship(
        "TaxonomyCategory", back_populates="rules"
    )


class LearningExample(Base):
    __tablename__ = "learning_examples"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant: Mapped[str] = mapped_column(String(255), index=True)
    description_normalized: Mapped[str] = mapped_column(Text)
    chosen_taxonomy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("taxonomy_categories.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    chosen_taxonomy: Mapped[TaxonomyCategory] = relationship("TaxonomyCategory")
