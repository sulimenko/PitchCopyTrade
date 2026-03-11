"""Initial foundation schema.

Revision ID: 20260310_0001
Revises:
Create Date: 2026-03-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260310_0001"
down_revision = None
branch_labels = None
depends_on = None


role_slug = sa.Enum("admin", "author", "moderator", name="role_slug")
user_status = sa.Enum("invited", "active", "blocked", name="user_status")
lead_source_type = sa.Enum("ads", "blogger", "organic", "direct", "referral", name="lead_source_type")
strategy_status = sa.Enum("draft", "published", "archived", name="strategy_status")
risk_level = sa.Enum("low", "medium", "high", name="risk_level")
product_type = sa.Enum("strategy", "author", "bundle", name="product_type")
billing_period = sa.Enum("month", "quarter", "year", name="billing_period")
payment_provider = sa.Enum("stub_manual", "tbank", name="payment_provider")
payment_status = sa.Enum(
    "created",
    "pending",
    "paid",
    "failed",
    "expired",
    "cancelled",
    "refunded",
    name="payment_status",
)
subscription_status = sa.Enum(
    "pending",
    "trial",
    "active",
    "expired",
    "cancelled",
    "blocked",
    name="subscription_status",
)
recommendation_kind = sa.Enum("new_idea", "update", "close", "cancel", name="recommendation_kind")
recommendation_status = sa.Enum(
    "draft",
    "review",
    "approved",
    "scheduled",
    "published",
    "closed",
    "cancelled",
    "archived",
    name="recommendation_status",
)
trade_side = sa.Enum("buy", "sell", name="trade_side")
legal_document_type = sa.Enum(
    "disclaimer",
    "offer",
    "privacy_policy",
    "payment_consent",
    name="legal_document_type",
)
instrument_type = sa.Enum("equity", name="instrument_type")


def upgrade() -> None:
    op.create_table(
        "lead_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("source_type", lead_source_type, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("ref_code", sa.String(length=120), nullable=True),
        sa.Column("utm_source", sa.String(length=120), nullable=True),
        sa.Column("utm_medium", sa.String(length=120), nullable=True),
        sa.Column("utm_campaign", sa.String(length=120), nullable=True),
        sa.Column("utm_content", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("ref_code", name="uq_lead_sources_ref_code"),
    )
    op.create_index("ix_lead_sources_source_type", "lead_sources", ["source_type"])

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("status", user_status, nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("lead_source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lead_source_id"], ["lead_sources.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("telegram_user_id", name="uq_users_telegram_user_id"),
    )

    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("slug", role_slug, nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", name="uq_roles_slug"),
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id", name="pk_user_roles"),
    )

    op.create_table(
        "author_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("requires_moderation", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("slug", name="uq_author_profiles_slug"),
        sa.UniqueConstraint("user_id", name="uq_author_profiles_user_id"),
    )

    op.create_table(
        "instruments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("board", sa.String(length=32), nullable=False),
        sa.Column("lot_size", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("instrument_type", instrument_type, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("ticker", name="uq_instruments_ticker"),
    )

    op.create_table(
        "strategies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("short_description", sa.String(length=500), nullable=False),
        sa.Column("full_description", sa.Text(), nullable=True),
        sa.Column("risk_level", risk_level, nullable=False),
        sa.Column("status", strategy_status, nullable=False),
        sa.Column("min_capital_rub", sa.Integer(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["author_profiles.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("slug", name="uq_strategies_slug"),
    )

    op.create_table(
        "bundles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", name="uq_bundles_slug"),
    )

    op.create_table(
        "bundle_members",
        sa.Column("bundle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["bundle_id"], ["bundles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("bundle_id", "strategy_id", name="pk_bundle_members"),
    )

    op.create_table(
        "subscription_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("product_type", product_type, nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("bundle_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("billing_period", billing_period, nullable=False),
        sa.Column("price_rub", sa.Integer(), nullable=False),
        sa.Column("trial_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("autorenew_allowed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("price_rub >= 0", name="ck_subscription_products_price_rub_non_negative"),
        sa.CheckConstraint("trial_days >= 0", name="ck_subscription_products_trial_days_non_negative"),
        sa.CheckConstraint(
            """
            (product_type = 'strategy' AND strategy_id IS NOT NULL AND author_id IS NULL AND bundle_id IS NULL)
            OR
            (product_type = 'author' AND author_id IS NOT NULL AND strategy_id IS NULL AND bundle_id IS NULL)
            OR
            (product_type = 'bundle' AND bundle_id IS NOT NULL AND strategy_id IS NULL AND author_id IS NULL)
            """,
            name="ck_subscription_products_target_matches_product_type",
        ),
        sa.ForeignKeyConstraint(["author_id"], ["author_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["bundle_id"], ["bundles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("slug", name="uq_subscription_products_slug"),
    )

    op.create_table(
        "promo_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("discount_percent", sa.Integer(), nullable=True),
        sa.Column("discount_amount_rub", sa.Integer(), nullable=True),
        sa.Column("max_redemptions", sa.Integer(), nullable=True),
        sa.Column("current_redemptions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("current_redemptions >= 0", name="ck_promo_codes_current_redemptions_non_negative"),
        sa.UniqueConstraint("code", name="uq_promo_codes_code"),
    )

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("promo_code_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", payment_provider, nullable=False),
        sa.Column("status", payment_status, nullable=False),
        sa.Column("amount_rub", sa.Integer(), nullable=False),
        sa.Column("discount_rub", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("final_amount_rub", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("stub_reference", sa.String(length=255), nullable=True),
        sa.Column("provider_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_rub >= 0", name="ck_payments_amount_rub_non_negative"),
        sa.CheckConstraint("discount_rub >= 0", name="ck_payments_discount_rub_non_negative"),
        sa.CheckConstraint("final_amount_rub >= 0", name="ck_payments_final_amount_rub_non_negative"),
        sa.ForeignKeyConstraint(["product_id"], ["subscription_products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["promo_code_id"], ["promo_codes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lead_source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("applied_promo_code_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", subscription_status, nullable=False),
        sa.Column("autorenew_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_trial", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("manual_discount_rub", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("manual_discount_rub >= 0", name="ck_subscriptions_manual_discount_rub_non_negative"),
        sa.CheckConstraint("end_at > start_at", name="ck_subscriptions_end_after_start"),
        sa.ForeignKeyConstraint(["applied_promo_code_id"], ["promo_codes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lead_source_id"], ["lead_sources.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["subscription_products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "legal_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("document_type", legal_document_type, nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("document_type", "version", name="uq_legal_documents_document_type_version"),
    )

    op.create_table(
        "user_consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["legal_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "document_id", "payment_id", name="uq_user_consents_user_document_payment"),
    )

    op.create_table(
        "recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("moderated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", recommendation_kind, nullable=False),
        sa.Column("status", recommendation_status, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("thesis", sa.Text(), nullable=True),
        sa.Column("market_context", sa.Text(), nullable=True),
        sa.Column("requires_moderation", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("moderation_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["author_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["moderated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "recommendation_legs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("side", trade_side, nullable=True),
        sa.Column("entry_from", sa.Numeric(18, 4), nullable=True),
        sa.Column("entry_to", sa.Numeric(18, 4), nullable=True),
        sa.Column("stop_loss", sa.Numeric(18, 4), nullable=True),
        sa.Column("take_profit_1", sa.Numeric(18, 4), nullable=True),
        sa.Column("take_profit_2", sa.Numeric(18, 4), nullable=True),
        sa.Column("take_profit_3", sa.Numeric(18, 4), nullable=True),
        sa.Column("time_horizon", sa.String(length=120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "entry_to IS NULL OR entry_from IS NULL OR entry_to >= entry_from",
            name="ck_recommendation_legs_entry_range_valid",
        ),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["recommendation_id"], ["recommendations.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "recommendation_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("storage_provider", sa.String(length=32), nullable=False),
        sa.Column("bucket_name", sa.String(length=120), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("size_bytes >= 0", name="ck_recommendation_attachments_size_bytes_non_negative"),
        sa.ForeignKeyConstraint(["recommendation_id"], ["recommendations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("recommendation_attachments")
    op.drop_table("recommendation_legs")
    op.drop_table("recommendations")
    op.drop_table("user_consents")
    op.drop_table("legal_documents")
    op.drop_table("subscriptions")
    op.drop_table("payments")
    op.drop_table("promo_codes")
    op.drop_table("subscription_products")
    op.drop_table("bundle_members")
    op.drop_table("bundles")
    op.drop_table("strategies")
    op.drop_table("instruments")
    op.drop_table("author_profiles")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_table("users")
    op.drop_index("ix_lead_sources_source_type", table_name="lead_sources")
    op.drop_table("lead_sources")

    bind = op.get_bind()
    for enum_obj in [
        instrument_type,
        legal_document_type,
        trade_side,
        recommendation_status,
        recommendation_kind,
        subscription_status,
        payment_status,
        payment_provider,
        billing_period,
        product_type,
        risk_level,
        strategy_status,
        lead_source_type,
        user_status,
        role_slug,
    ]:
        enum_obj.drop(bind, checkfirst=True)
