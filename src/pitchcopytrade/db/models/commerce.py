from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pitchcopytrade.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from pitchcopytrade.db.models.enums import LegalDocumentType, PaymentProvider, PaymentStatus, SubscriptionStatus, sql_enum

if TYPE_CHECKING:
    from pitchcopytrade.db.models.accounts import User
    from pitchcopytrade.db.models.catalog import LeadSource, SubscriptionProduct


class PromoCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "promo_codes"
    __table_args__ = (
        UniqueConstraint("code", name="uq_promo_codes_code"),
        CheckConstraint("current_redemptions >= 0", name="current_redemptions_non_negative"),
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    discount_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discount_amount_rub: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_redemptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_redemptions: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    payments: Mapped[list["Payment"]] = relationship(back_populates="promo_code")
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="applied_promo_code")


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_rub >= 0", name="amount_rub_non_negative"),
        CheckConstraint("discount_rub >= 0", name="discount_rub_non_negative"),
        CheckConstraint("final_amount_rub >= 0", name="final_amount_rub_non_negative"),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[str] = mapped_column(ForeignKey("subscription_products.id", ondelete="RESTRICT"), nullable=False)
    promo_code_id: Mapped[str | None] = mapped_column(ForeignKey("promo_codes.id", ondelete="SET NULL"), nullable=True)
    provider: Mapped[PaymentProvider] = mapped_column(
        sql_enum(PaymentProvider, name="payment_provider"),
        default=PaymentProvider.STUB_MANUAL,
        nullable=False,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        sql_enum(PaymentStatus, name="payment_status"),
        default=PaymentStatus.CREATED,
        nullable=False,
    )
    amount_rub: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_rub: Mapped[int] = mapped_column(Integer, default=0)
    final_amount_rub: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stub_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="payments")
    product: Mapped["SubscriptionProduct"] = relationship(back_populates="payments")
    promo_code: Mapped["PromoCode | None"] = relationship(back_populates="payments")
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="payment")
    consents: Mapped[list["UserConsent"]] = relationship(back_populates="payment")


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint("manual_discount_rub >= 0", name="manual_discount_rub_non_negative"),
        CheckConstraint("end_at > start_at", name="end_after_start"),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[str] = mapped_column(ForeignKey("subscription_products.id", ondelete="RESTRICT"), nullable=False)
    payment_id: Mapped[str | None] = mapped_column(ForeignKey("payments.id", ondelete="SET NULL"), nullable=True)
    lead_source_id: Mapped[str | None] = mapped_column(ForeignKey("lead_sources.id", ondelete="SET NULL"), nullable=True)
    applied_promo_code_id: Mapped[str | None] = mapped_column(ForeignKey("promo_codes.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[SubscriptionStatus] = mapped_column(
        sql_enum(SubscriptionStatus, name="subscription_status"),
        default=SubscriptionStatus.PENDING,
        nullable=False,
    )
    autorenew_enabled: Mapped[bool] = mapped_column(default=False)
    is_trial: Mapped[bool] = mapped_column(default=False)
    manual_discount_rub: Mapped[int] = mapped_column(Integer, default=0)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship(back_populates="subscriptions")
    product: Mapped["SubscriptionProduct"] = relationship(back_populates="subscriptions")
    payment: Mapped["Payment | None"] = relationship(back_populates="subscriptions")
    lead_source: Mapped["LeadSource | None"] = relationship(back_populates="subscriptions")
    applied_promo_code: Mapped["PromoCode | None"] = relationship(back_populates="subscriptions")


class LegalDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "legal_documents"
    __table_args__ = (UniqueConstraint("document_type", "version", name="uq_legal_documents_document_type_version"),)

    document_type: Mapped[LegalDocumentType] = mapped_column(
        sql_enum(LegalDocumentType, name="legal_document_type"),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    source_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    consents: Mapped[list["UserConsent"]] = relationship(back_populates="document")


class UserConsent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_consents"
    __table_args__ = (
        UniqueConstraint("user_id", "document_id", "payment_id", name="uq_user_consents_user_document_payment"),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("legal_documents.id", ondelete="CASCADE"), nullable=False)
    payment_id: Mapped[str | None] = mapped_column(ForeignKey("payments.id", ondelete="SET NULL"), nullable=True)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user: Mapped["User"] = relationship(back_populates="consents")
    document: Mapped["LegalDocument"] = relationship(back_populates="consents")
    payment: Mapped["Payment | None"] = relationship(back_populates="consents")
