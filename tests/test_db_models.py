from __future__ import annotations

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import configure_mappers

from pitchcopytrade.db.models import Base
from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Bundle, LeadSource, Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import LegalDocument, Payment, PromoCode, Subscription, UserConsent
from pitchcopytrade.db.models.content import Recommendation, RecommendationAttachment, RecommendationLeg


def test_metadata_contains_required_foundation_tables() -> None:
    expected_tables = {
        "users",
        "roles",
        "user_roles",
        "author_profiles",
        "instruments",
        "strategies",
        "bundles",
        "bundle_members",
        "subscription_products",
        "lead_sources",
        "promo_codes",
        "payments",
        "subscriptions",
        "recommendations",
        "recommendation_legs",
        "recommendation_attachments",
        "legal_documents",
        "user_consents",
        "audit_events",
    }

    assert expected_tables.issubset(Base.metadata.tables.keys())


def test_subscription_product_has_target_integrity_check() -> None:
    table = SubscriptionProduct.__table__
    check_names = {constraint.name for constraint in table.constraints if isinstance(constraint, CheckConstraint)}

    assert "ck_subscription_products_target_matches_product_type" in check_names
    assert "ck_subscription_products_price_rub_non_negative" in check_names
    assert "ck_subscription_products_trial_days_non_negative" in check_names


def test_commerce_and_content_constraints_exist() -> None:
    payment_checks = {constraint.name for constraint in Payment.__table__.constraints if isinstance(constraint, CheckConstraint)}
    subscription_checks = {
        constraint.name for constraint in Subscription.__table__.constraints if isinstance(constraint, CheckConstraint)
    }
    attachment_checks = {
        constraint.name
        for constraint in RecommendationAttachment.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "ck_payments_amount_rub_non_negative" in payment_checks
    assert "ck_subscriptions_end_after_start" in subscription_checks
    assert "ck_recommendation_attachments_size_bytes_non_negative" in attachment_checks


def test_unique_constraints_cover_roles_legal_and_consents() -> None:
    legal_uniques = {constraint.name for constraint in LegalDocument.__table__.constraints if isinstance(constraint, UniqueConstraint)}
    consent_uniques = {constraint.name for constraint in UserConsent.__table__.constraints if isinstance(constraint, UniqueConstraint)}
    promo_uniques = {constraint.name for constraint in PromoCode.__table__.constraints if isinstance(constraint, UniqueConstraint)}

    assert "uq_legal_documents_document_type_version" in legal_uniques
    assert "uq_user_consents_user_document_payment" in consent_uniques
    assert "uq_promo_codes_code" in promo_uniques


def test_relationships_support_acl_and_multi_author_content() -> None:
    configure_mappers()

    assert User.lead_source.property.mapper.class_ is LeadSource
    assert AuthorProfile.strategies.property.mapper.class_ is Strategy
    assert Strategy.author.property.mapper.class_ is AuthorProfile
    assert SubscriptionProduct.bundle.property.mapper.class_ is Bundle
    assert Recommendation.author.property.mapper.class_ is AuthorProfile
    assert RecommendationLeg.recommendation.property.mapper.class_ is Recommendation
