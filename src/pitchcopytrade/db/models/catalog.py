from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pitchcopytrade.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from pitchcopytrade.db.models.enums import (
    BillingPeriod,
    InstrumentType,
    LeadSourceType,
    ProductType,
    RiskLevel,
    StrategyStatus,
    sql_enum,
)

if TYPE_CHECKING:
    from pitchcopytrade.db.models.accounts import AuthorProfile, User
    from pitchcopytrade.db.models.commerce import Payment, Subscription
    from pitchcopytrade.db.models.content import Recommendation, RecommendationLeg


class LeadSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lead_sources"

    source_type: Mapped[LeadSourceType] = mapped_column(sql_enum(LeadSourceType, name="lead_source_type"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    ref_code: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True)
    utm_source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(120), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(120), nullable=True)
    utm_content: Mapped[str | None] = mapped_column(String(120), nullable=True)

    users: Mapped[list["User"]] = relationship(back_populates="lead_source")
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="lead_source")


class Instrument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "instruments"
    __table_args__ = (UniqueConstraint("ticker", name="uq_instruments_ticker"),)

    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    board: Mapped[str] = mapped_column(String(32), nullable=False)
    lot_size: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    instrument_type: Mapped[InstrumentType] = mapped_column(
        sql_enum(InstrumentType, name="instrument_type"),
        default=InstrumentType.EQUITY,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(default=True)

    recommendation_legs: Mapped[list["RecommendationLeg"]] = relationship(back_populates="instrument")
    watchlist_authors: Mapped[list["AuthorProfile"]] = relationship(
        secondary="author_watchlist_instruments",
        back_populates="watchlist_instruments",
    )


class Strategy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "strategies"
    __table_args__ = (UniqueConstraint("slug", name="uq_strategies_slug"),)

    author_id: Mapped[str] = mapped_column(ForeignKey("author_profiles.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    short_description: Mapped[str] = mapped_column(String(500), nullable=False)
    full_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[RiskLevel] = mapped_column(sql_enum(RiskLevel, name="risk_level"), nullable=False)
    status: Mapped[StrategyStatus] = mapped_column(
        sql_enum(StrategyStatus, name="strategy_status"),
        default=StrategyStatus.DRAFT,
        nullable=False,
    )
    min_capital_rub: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_public: Mapped[bool] = mapped_column(default=False)

    author: Mapped["AuthorProfile"] = relationship(back_populates="strategies")
    bundle_memberships: Mapped[list["BundleMember"]] = relationship(back_populates="strategy")
    subscription_products: Mapped[list["SubscriptionProduct"]] = relationship(back_populates="strategy")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="strategy")


class Bundle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bundles"
    __table_args__ = (UniqueConstraint("slug", name="uq_bundles_slug"),)

    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)

    members: Mapped[list["BundleMember"]] = relationship(back_populates="bundle")
    subscription_products: Mapped[list["SubscriptionProduct"]] = relationship(back_populates="bundle")


class BundleMember(Base):
    __tablename__ = "bundle_members"

    bundle_id: Mapped[str] = mapped_column(ForeignKey("bundles.id", ondelete="CASCADE"), primary_key=True)
    strategy_id: Mapped[str] = mapped_column(ForeignKey("strategies.id", ondelete="CASCADE"), primary_key=True)

    bundle: Mapped[Bundle] = relationship(back_populates="members")
    strategy: Mapped[Strategy] = relationship(back_populates="bundle_memberships")


class SubscriptionProduct(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscription_products"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_subscription_products_slug"),
        CheckConstraint("price_rub >= 0", name="price_rub_non_negative"),
        CheckConstraint("trial_days >= 0", name="trial_days_non_negative"),
        CheckConstraint(
            """
            (product_type = 'strategy' AND strategy_id IS NOT NULL AND author_id IS NULL AND bundle_id IS NULL)
            OR
            (product_type = 'author' AND author_id IS NOT NULL AND strategy_id IS NULL AND bundle_id IS NULL)
            OR
            (product_type = 'bundle' AND bundle_id IS NOT NULL AND strategy_id IS NULL AND author_id IS NULL)
            """,
            name="target_matches_product_type",
        ),
    )

    product_type: Mapped[ProductType] = mapped_column(sql_enum(ProductType, name="product_type"), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategy_id: Mapped[str | None] = mapped_column(ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True)
    author_id: Mapped[str | None] = mapped_column(ForeignKey("author_profiles.id", ondelete="SET NULL"), nullable=True)
    bundle_id: Mapped[str | None] = mapped_column(ForeignKey("bundles.id", ondelete="SET NULL"), nullable=True)
    billing_period: Mapped[BillingPeriod] = mapped_column(sql_enum(BillingPeriod, name="billing_period"), nullable=False)
    price_rub: Mapped[int] = mapped_column(Integer, nullable=False)
    trial_days: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    autorenew_allowed: Mapped[bool] = mapped_column(default=True)

    strategy: Mapped["Strategy | None"] = relationship(back_populates="subscription_products")
    author: Mapped["AuthorProfile | None"] = relationship(back_populates="subscription_products")
    bundle: Mapped["Bundle | None"] = relationship(back_populates="subscription_products")
    payments: Mapped[list["Payment"]] = relationship(back_populates="product")
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="product")
