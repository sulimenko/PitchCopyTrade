from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Bundle, Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import Payment, Subscription, UserConsent
from pitchcopytrade.db.models.content import Recommendation
from pitchcopytrade.db.models.enums import (
    BillingPeriod,
    PaymentStatus,
    ProductType,
    RiskLevel,
    StrategyStatus,
    SubscriptionStatus,
)


@dataclass(slots=True)
class AdminDashboardStats:
    authors_total: int
    strategies_total: int
    strategies_public: int
    active_subscriptions: int
    recommendations_live: int


@dataclass(slots=True)
class StrategyFormData:
    author_id: str
    slug: str
    title: str
    short_description: str
    full_description: str | None
    risk_level: RiskLevel
    status: StrategyStatus
    min_capital_rub: int | None
    is_public: bool


@dataclass(slots=True)
class ProductFormData:
    product_type: ProductType
    slug: str
    title: str
    description: str | None
    strategy_id: str | None
    author_id: str | None
    bundle_id: str | None
    billing_period: BillingPeriod
    price_rub: int
    trial_days: int
    is_active: bool
    autorenew_allowed: bool


@dataclass(slots=True)
class PaymentReviewStats:
    pending_payments: int
    paid_payments: int
    pending_subscriptions: int
    active_subscriptions: int


async def get_admin_dashboard_stats(session: AsyncSession) -> AdminDashboardStats:
    authors_total = await _count_query(session, select(func.count(AuthorProfile.id)))
    strategies_total = await _count_query(session, select(func.count(Strategy.id)))
    strategies_public = await _count_query(session, select(func.count(Strategy.id)).where(Strategy.is_public.is_(True)))
    active_subscriptions = await _count_query(
        session,
        select(func.count(Subscription.id)).where(
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL])
        ),
    )
    recommendations_live = await _count_query(
        session,
        select(func.count(Recommendation.id)).where(Recommendation.published_at.is_not(None)),
    )
    return AdminDashboardStats(
        authors_total=authors_total,
        strategies_total=strategies_total,
        strategies_public=strategies_public,
        active_subscriptions=active_subscriptions,
        recommendations_live=recommendations_live,
    )


async def list_admin_strategies(session: AsyncSession) -> list[Strategy]:
    query = (
        select(Strategy)
        .options(selectinload(Strategy.author).selectinload(AuthorProfile.user))
        .order_by(Strategy.created_at.desc(), Strategy.title.asc())
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def list_admin_authors(session: AsyncSession) -> list[AuthorProfile]:
    query = (
        select(AuthorProfile)
        .options(selectinload(AuthorProfile.user))
        .where(AuthorProfile.is_active.is_(True))
        .order_by(AuthorProfile.display_name.asc())
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_admin_strategy(session: AsyncSession, strategy_id: str) -> Strategy | None:
    query = (
        select(Strategy)
        .options(selectinload(Strategy.author).selectinload(AuthorProfile.user))
        .where(Strategy.id == strategy_id)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def list_admin_products(session: AsyncSession) -> list[SubscriptionProduct]:
    query = (
        select(SubscriptionProduct)
        .options(
            selectinload(SubscriptionProduct.strategy).selectinload(Strategy.author),
            selectinload(SubscriptionProduct.author).selectinload(AuthorProfile.user),
            selectinload(SubscriptionProduct.bundle),
        )
        .order_by(SubscriptionProduct.created_at.desc(), SubscriptionProduct.title.asc())
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_admin_product(session: AsyncSession, product_id: str) -> SubscriptionProduct | None:
    query = (
        select(SubscriptionProduct)
        .options(
            selectinload(SubscriptionProduct.strategy).selectinload(Strategy.author),
            selectinload(SubscriptionProduct.author).selectinload(AuthorProfile.user),
            selectinload(SubscriptionProduct.bundle),
        )
        .where(SubscriptionProduct.id == product_id)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def list_admin_bundles(session: AsyncSession) -> list[Bundle]:
    query = select(Bundle).where(Bundle.is_active.is_(True)).order_by(Bundle.title.asc())
    result = await session.execute(query)
    return list(result.scalars().all())


async def list_admin_payments(session: AsyncSession) -> list[Payment]:
    query = (
        select(Payment)
        .options(
            selectinload(Payment.user),
            selectinload(Payment.product).selectinload(SubscriptionProduct.strategy),
            selectinload(Payment.subscriptions),
            selectinload(Payment.consents),
        )
        .order_by(Payment.created_at.desc())
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_admin_payment(session: AsyncSession, payment_id: str) -> Payment | None:
    query = (
        select(Payment)
        .options(
            selectinload(Payment.user),
            selectinload(Payment.product).selectinload(SubscriptionProduct.strategy),
            selectinload(Payment.product).selectinload(SubscriptionProduct.author),
            selectinload(Payment.subscriptions).selectinload(Subscription.product),
            selectinload(Payment.consents).selectinload(UserConsent.document),
        )
        .where(Payment.id == payment_id)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_payment_review_stats(session: AsyncSession) -> PaymentReviewStats:
    pending_payments = await _count_query(
        session,
        select(func.count(Payment.id)).where(Payment.status == PaymentStatus.PENDING),
    )
    paid_payments = await _count_query(
        session,
        select(func.count(Payment.id)).where(Payment.status == PaymentStatus.PAID),
    )
    pending_subscriptions = await _count_query(
        session,
        select(func.count(Subscription.id)).where(Subscription.status == SubscriptionStatus.PENDING),
    )
    active_subscriptions = await _count_query(
        session,
        select(func.count(Subscription.id)).where(
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL])
        ),
    )
    return PaymentReviewStats(
        pending_payments=pending_payments,
        paid_payments=paid_payments,
        pending_subscriptions=pending_subscriptions,
        active_subscriptions=active_subscriptions,
    )


async def create_strategy(session: AsyncSession, data: StrategyFormData) -> Strategy:
    strategy = Strategy(
        author_id=data.author_id,
        slug=data.slug,
        title=data.title,
        short_description=data.short_description,
        full_description=data.full_description,
        risk_level=data.risk_level,
        status=data.status,
        min_capital_rub=data.min_capital_rub,
        is_public=data.is_public,
    )
    session.add(strategy)
    await session.commit()
    await session.refresh(strategy)
    return strategy


async def create_product(session: AsyncSession, data: ProductFormData) -> SubscriptionProduct:
    product = SubscriptionProduct(
        product_type=data.product_type,
        slug=data.slug,
        title=data.title,
        description=data.description,
        strategy_id=data.strategy_id,
        author_id=data.author_id,
        bundle_id=data.bundle_id,
        billing_period=data.billing_period,
        price_rub=data.price_rub,
        trial_days=data.trial_days,
        is_active=data.is_active,
        autorenew_allowed=data.autorenew_allowed,
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product


async def update_strategy(session: AsyncSession, strategy: Strategy, data: StrategyFormData) -> Strategy:
    strategy.author_id = data.author_id
    strategy.slug = data.slug
    strategy.title = data.title
    strategy.short_description = data.short_description
    strategy.full_description = data.full_description
    strategy.risk_level = data.risk_level
    strategy.status = data.status
    strategy.min_capital_rub = data.min_capital_rub
    strategy.is_public = data.is_public
    await session.commit()
    await session.refresh(strategy)
    return strategy


async def update_product(
    session: AsyncSession, product: SubscriptionProduct, data: ProductFormData
) -> SubscriptionProduct:
    product.product_type = data.product_type
    product.slug = data.slug
    product.title = data.title
    product.description = data.description
    product.strategy_id = data.strategy_id
    product.author_id = data.author_id
    product.bundle_id = data.bundle_id
    product.billing_period = data.billing_period
    product.price_rub = data.price_rub
    product.trial_days = data.trial_days
    product.is_active = data.is_active
    product.autorenew_allowed = data.autorenew_allowed
    await session.commit()
    await session.refresh(product)
    return product


async def confirm_payment_and_activate_subscription(
    session: AsyncSession,
    payment: Payment,
    *,
    confirmed_at: datetime | None = None,
) -> tuple[Payment, list[Subscription]]:
    if payment.status is PaymentStatus.PAID:
        return payment, payment.subscriptions
    if payment.status is not PaymentStatus.PENDING:
        raise ValueError("Подтверждать можно только payment в статусе pending")

    if not payment.subscriptions:
        raise ValueError("У платежа нет связанной подписки")

    timestamp = confirmed_at or datetime.now(timezone.utc)
    payment.status = PaymentStatus.PAID
    payment.confirmed_at = timestamp

    for subscription in payment.subscriptions:
        subscription.status = SubscriptionStatus.TRIAL if subscription.is_trial else SubscriptionStatus.ACTIVE

    await session.commit()
    await session.refresh(payment)
    for subscription in payment.subscriptions:
        await session.refresh(subscription)
    return payment, payment.subscriptions


async def _count_query(session: AsyncSession, query: Any) -> int:
    result = await session.execute(query)
    return int(result.scalar_one() or 0)
