"""Initial schema – all tables.

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Taxonomy Categories ────────────────────────────────────────────────────
    op.create_table(
        "taxonomy_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("taxonomy_categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ynab_category_id", sa.String(64), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
    )
    op.create_index("ix_taxonomy_categories_name", "taxonomy_categories", ["name"])

    # ── Receipts ───────────────────────────────────────────────────────────────
    op.create_table(
        "receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("merchant", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False, server_default="upload"),
        sa.Column("purchase_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=True),
        sa.Column("tax", sa.Numeric(12, 2), nullable=True),
        sa.Column("total", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("payment_method_last4", sa.String(4), nullable=True),
        sa.Column("parse_confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("parse_notes", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_receipts_merchant", "receipts", ["merchant"])

    # ── Line Items ─────────────────────────────────────────────────────────────
    op.create_table(
        "line_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description_raw", sa.Text, nullable=False),
        sa.Column("description_normalized", sa.Text, nullable=False),
        sa.Column("sku", sa.String(64), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 4), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("discounts", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tax_flag", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("department_hint", sa.String(128), nullable=True),
        sa.Column("taxonomy_category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("taxonomy_categories.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_line_items_receipt_id", "line_items", ["receipt_id"])
    op.create_index("ix_line_items_description_normalized", "line_items", ["description_normalized"])

    # ── Artifacts ─────────────────────────────────────────────────────────────
    op.create_table(
        "artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_file_uri", sa.Text, nullable=False),
        sa.Column("extracted_text", sa.Text, nullable=True),
        sa.Column("raw_source_json", sa.Text, nullable=True),
        sa.Column("mime_type", sa.String(128), nullable=False, server_default="text/plain"),
        sa.Column("file_size", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_artifacts_receipt_id", "artifacts", ["receipt_id"])

    # ── YNAB Tokens ────────────────────────────────────────────────────────────
    op.create_table(
        "ynab_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False, server_default="default"),
        sa.Column("access_token_enc", sa.Text, nullable=False),
        sa.Column("refresh_token_enc", sa.Text, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("budget_id", sa.String(64), nullable=True),
    )
    op.create_index("ix_ynab_tokens_user_id", "ynab_tokens", ["user_id"])

    # ── YNAB Links ─────────────────────────────────────────────────────────────
    op.create_table(
        "ynab_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ynab_transaction_id", sa.String(64), nullable=False),
        sa.Column("match_score", sa.Float, nullable=False, server_default="0"),
        sa.Column("linked_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("purpose_tag", sa.String(32), nullable=True),
        sa.Column("return_by_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reimburser", sa.String(128), nullable=True),
    )
    op.create_index("ix_ynab_links_receipt_id", "ynab_links", ["receipt_id"])
    op.create_index("ix_ynab_links_ynab_transaction_id", "ynab_links", ["ynab_transaction_id"])

    # ── YNAB Split Proposals ───────────────────────────────────────────────────
    op.create_table(
        "ynab_split_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ynab_transaction_id", sa.String(64), nullable=False),
        sa.Column("proposal_json", postgresql.JSON, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ynab_split_proposals_receipt_id", "ynab_split_proposals", ["receipt_id"])

    # ── Category Rules ─────────────────────────────────────────────────────────
    op.create_table(
        "category_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("rule_type", sa.String(32), nullable=False),
        sa.Column("pattern", sa.Text, nullable=False),
        sa.Column("merchant_filter", sa.String(255), nullable=True),
        sa.Column("department_filter", sa.String(128), nullable=True),
        sa.Column("taxonomy_category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("taxonomy_categories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
    )

    # ── Learning Examples ──────────────────────────────────────────────────────
    op.create_table(
        "learning_examples",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("merchant", sa.String(255), nullable=False),
        sa.Column("description_normalized", sa.Text, nullable=False),
        sa.Column("chosen_taxonomy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("taxonomy_categories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_learning_examples_merchant", "learning_examples", ["merchant"])

    # ── Audit Logs ─────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("before_json", sa.Text, nullable=True),
        sa.Column("after_json", sa.Text, nullable=True),
        sa.Column("user_id", sa.String(64), nullable=False, server_default="default"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])

    # ── User Settings ──────────────────────────────────────────────────────────
    op.create_table(
        "user_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False, unique=True),
        sa.Column("default_budget_id", sa.String(64), nullable=True),
        sa.Column("default_account_id", sa.String(64), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("notifications_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_user_settings_user_id", "user_settings", ["user_id"])


def downgrade() -> None:
    op.drop_table("user_settings")
    op.drop_table("audit_logs")
    op.drop_table("learning_examples")
    op.drop_table("category_rules")
    op.drop_table("ynab_split_proposals")
    op.drop_table("ynab_links")
    op.drop_table("ynab_tokens")
    op.drop_table("artifacts")
    op.drop_table("line_items")
    op.drop_table("receipts")
    op.drop_table("taxonomy_categories")
