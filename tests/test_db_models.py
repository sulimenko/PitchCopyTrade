from __future__ import annotations

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import configure_mappers

from pitchcopytrade.db.models import Base
from pitchcopytrade.db.models.accounts import AuthorProfile, Role, User
from pitchcopytrade.db.models.catalog import Bundle, LeadSource, Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import LegalDocument, Payment, PromoCode, Subscription, UserConsent
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.notification_log import NotificationLog


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
        "messages",
        "legal_documents",
        "user_consents",
        "audit_events",
        "notification_log",
    }

    assert expected_tables.issubset(Base.metadata.tables.keys())


def test_subscription_product_has_target_integrity_check() -> None:
    table = SubscriptionProduct.__table__
    check_names = {constraint.name for constraint in table.constraints if isinstance(constraint, CheckConstraint)}

    assert "target_matches_product_type" in check_names
    assert "price_rub_non_negative" in check_names
    assert "trial_days_non_negative" in check_names


def test_commerce_and_content_constraints_exist() -> None:
    payment_checks = {constraint.name for constraint in Payment.__table__.constraints if isinstance(constraint, CheckConstraint)}
    subscription_checks = {
        constraint.name for constraint in Subscription.__table__.constraints if isinstance(constraint, CheckConstraint)
    }

    assert "amount_rub_non_negative" in payment_checks
    assert "end_after_start" in subscription_checks


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
    assert AuthorProfile.messages.property.mapper.class_ is Message
    assert Strategy.author.property.mapper.class_ is AuthorProfile
    assert Strategy.messages.property.mapper.class_ is Message
    assert SubscriptionProduct.bundle.property.mapper.class_ is Bundle
    assert Bundle.messages.property.mapper.class_ is Message
    assert Message.author.property.mapper.class_ is AuthorProfile
    assert Message.user.property.mapper.class_ is User
    assert Message.moderator.property.mapper.class_ is User
    assert Message.strategy.property.mapper.class_ is Strategy
    assert Message.bundle.property.mapper.class_ is Bundle
    assert NotificationLog.message.property.mapper.class_ is Message


def test_sqlalchemy_enums_persist_enum_values_not_names() -> None:
    assert User.__table__.c.status.type.enums == ["invited", "active", "inactive"]
    assert Role.__table__.c.slug.type.enums == ["admin", "author", "moderator"]
    assert Payment.__table__.c.status.type.enums == [
        "created",
        "pending",
        "paid",
        "failed",
        "expired",
        "cancelled",
        "refunded",
    ]
    assert Subscription.__table__.c.status.type.enums == [
        "pending",
        "trial",
        "active",
        "expired",
        "cancelled",
        "blocked",
    ]
    assert Message.__table__.c.status.type.length == 32
    assert Message.__table__.c.moderation.type.length == 32
    assert Message.__table__.c.channel.type.item_type.length == 32
    assert Message.__table__.c.documents.type.__class__.__name__ == "JSONB"
    assert NotificationLog.__table__.c.channel.type.enums == ["telegram", "email"]
