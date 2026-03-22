from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any

from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.accounts import AuthorProfile, Role, User, user_roles
from pitchcopytrade.db.models.audit import AuditEvent
from pitchcopytrade.db.models.catalog import Bundle, Instrument, Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import Payment, Subscription, UserConsent
from pitchcopytrade.db.models.content import Recommendation
from pitchcopytrade.db.models.enums import (
    BillingPeriod,
    InviteDeliveryStatus,
    PaymentStatus,
    ProductType,
    RiskLevel,
    RoleSlug,
    StrategyStatus,
    SubscriptionStatus,
    UserStatus,
)
from pitchcopytrade.auth.session import build_staff_invite_bot_link, build_staff_invite_link, build_staff_invite_token
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore
from pitchcopytrade.services.promo import sync_promo_redemption_counter

logger = logging.getLogger(__name__)


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


@dataclass(slots=True)
class StaffCreateData:
    display_name: str
    email: str | None
    telegram_user_id: int | None
    role_slugs: tuple[RoleSlug, ...]


@dataclass(slots=True)
class StaffUpdateData:
    display_name: str
    email: str | None
    telegram_user_id: int | None
    role_slugs: tuple[RoleSlug, ...]


@dataclass(slots=True)
class AdminAuthorUpdateData:
    display_name: str
    email: str | None
    telegram_user_id: int | None
    role_slugs: tuple[RoleSlug, ...]
    requires_moderation: bool
    is_active: bool


async def list_admin_subscriptions(
    session: AsyncSession | None,
    *,
    query_text: str | None = None,
) -> list[Subscription]:
    if session is None:
        graph, _store = _file_admin_graph()
        items = list(graph.subscriptions.values())
        items.sort(key=lambda item: (item.start_at, item.created_at), reverse=True)
        return _filter_admin_subscriptions(items, query_text)
    query = (
        select(Subscription)
        .options(
            selectinload(Subscription.user),
            selectinload(Subscription.product).selectinload(SubscriptionProduct.strategy),
            selectinload(Subscription.product).selectinload(SubscriptionProduct.author).selectinload(AuthorProfile.user),
            selectinload(Subscription.product).selectinload(SubscriptionProduct.bundle),
            selectinload(Subscription.payment),
            selectinload(Subscription.lead_source),
        )
        .order_by(Subscription.start_at.desc(), Subscription.created_at.desc())
    )
    result = await session.execute(query)
    items = list(result.scalars().all())
    return _filter_admin_subscriptions(items, query_text)


async def get_admin_subscription(session: AsyncSession | None, subscription_id: str) -> Subscription | None:
    if session is None:
        graph, _store = _file_admin_graph()
        return graph.subscriptions.get(subscription_id)
    query = (
        select(Subscription)
        .options(
            selectinload(Subscription.user),
            selectinload(Subscription.product).selectinload(SubscriptionProduct.strategy),
            selectinload(Subscription.product).selectinload(SubscriptionProduct.author).selectinload(AuthorProfile.user),
            selectinload(Subscription.product).selectinload(SubscriptionProduct.bundle),
            selectinload(Subscription.payment),
            selectinload(Subscription.lead_source),
        )
        .where(Subscription.id == subscription_id)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


def _file_admin_graph() -> tuple[FileDatasetGraph, FileDataStore]:
    store = FileDataStore()
    graph = FileDatasetGraph.load(store)
    return graph, store


async def get_admin_dashboard_stats(session: AsyncSession | None) -> AdminDashboardStats:
    if session is None:
        graph, _store = _file_admin_graph()
        return AdminDashboardStats(
            authors_total=sum(1 for item in graph.authors.values() if item.is_active),
            strategies_total=len(graph.strategies),
            strategies_public=sum(1 for item in graph.strategies.values() if item.is_public),
            active_subscriptions=sum(
                1 for item in graph.subscriptions.values() if item.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]
            ),
            recommendations_live=sum(1 for item in graph.recommendations.values() if item.published_at is not None),
        )
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


async def list_admin_strategies(session: AsyncSession | None) -> list[Strategy]:
    if session is None:
        graph, _store = _file_admin_graph()
        items = list(graph.strategies.values())
        items.sort(key=lambda item: (item.created_at, item.title.lower()), reverse=True)
        return items
    query = (
        select(Strategy)
        .options(selectinload(Strategy.author).selectinload(AuthorProfile.user))
        .order_by(Strategy.created_at.desc(), Strategy.title.asc())
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def list_admin_authors(session: AsyncSession | None, *, status_filter: str = "all") -> list[AuthorProfile]:
    if session is None:
        graph, _store = _file_admin_graph()
        items = list(graph.authors.values())
        if status_filter == "active":
            items = [item for item in items if item.is_active]
        elif status_filter == "inactive":
            items = [item for item in items if not item.is_active]
        items.sort(key=lambda item: ((item.display_name or item.slug or item.id or "")).lower())
        return items
    query = (
        select(AuthorProfile)
        .options(selectinload(AuthorProfile.user).selectinload(User.roles))
        .order_by(AuthorProfile.display_name.asc())
    )
    if status_filter == "active":
        query = query.where(AuthorProfile.is_active.is_(True))
    elif status_filter == "inactive":
        query = query.where(AuthorProfile.is_active.is_(False))
    result = await session.execute(query)
    return list(result.scalars().all())


async def list_admin_staff(session: AsyncSession | None, *, role_filter: str = "all") -> list[User]:
    if session is None:
        graph, _store = _file_admin_graph()
        items = [item for item in graph.users.values() if _is_staff_user(item)]
        filtered = [item for item in items if _matches_staff_role_filter(item, role_filter)]
        filtered.sort(key=_staff_sort_key)
        return filtered
    query = (
        select(User)
        .options(selectinload(User.roles), selectinload(User.author_profile))
        .order_by(User.created_at.desc(), User.full_name.asc(), User.email.asc())
    )
    result = await session.execute(query)
    items = [item for item in result.scalars().all() if _is_staff_user(item)]
    return [item for item in items if _matches_staff_role_filter(item, role_filter)]


async def get_admin_strategy(session: AsyncSession | None, strategy_id: str) -> Strategy | None:
    if session is None:
        graph, _store = _file_admin_graph()
        return graph.strategies.get(strategy_id)
    query = (
        select(Strategy)
        .options(selectinload(Strategy.author).selectinload(AuthorProfile.user))
        .where(Strategy.id == strategy_id)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def list_admin_products(session: AsyncSession | None) -> list[SubscriptionProduct]:
    if session is None:
        graph, _store = _file_admin_graph()
        items = list(graph.products.values())
        items.sort(key=lambda item: (item.created_at, item.title.lower()), reverse=True)
        return items
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


async def get_admin_product(session: AsyncSession | None, product_id: str) -> SubscriptionProduct | None:
    if session is None:
        graph, _store = _file_admin_graph()
        return graph.products.get(product_id)
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


async def list_admin_bundles(session: AsyncSession | None) -> list[Bundle]:
    if session is None:
        graph, _store = _file_admin_graph()
        items = [item for item in graph.bundles.values() if item.is_active]
        items.sort(key=lambda item: item.title.lower())
        return items
    query = select(Bundle).where(Bundle.is_active.is_(True)).order_by(Bundle.title.asc())
    result = await session.execute(query)
    return list(result.scalars().all())


async def list_admin_payments(session: AsyncSession | None) -> list[Payment]:
    if session is None:
        graph, _store = _file_admin_graph()
        items = list(graph.payments.values())
        items.sort(key=lambda item: item.created_at, reverse=True)
        return items
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


async def get_admin_payment(session: AsyncSession | None, payment_id: str) -> Payment | None:
    if session is None:
        graph, _store = _file_admin_graph()
        return graph.payments.get(payment_id)
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


async def get_payment_review_stats(session: AsyncSession | None) -> PaymentReviewStats:
    if session is None:
        graph, _store = _file_admin_graph()
        return PaymentReviewStats(
            pending_payments=sum(1 for item in graph.payments.values() if item.status == PaymentStatus.PENDING),
            paid_payments=sum(1 for item in graph.payments.values() if item.status == PaymentStatus.PAID),
            pending_subscriptions=sum(1 for item in graph.subscriptions.values() if item.status == SubscriptionStatus.PENDING),
            active_subscriptions=sum(
                1 for item in graph.subscriptions.values() if item.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]
            ),
        )
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


async def create_strategy(session: AsyncSession | None, data: StrategyFormData) -> Strategy:
    if session is None:
        graph, store = _file_admin_graph()
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
        graph.add(strategy)
        graph.save(store)
        return strategy
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


async def create_product(session: AsyncSession | None, data: ProductFormData) -> SubscriptionProduct:
    if session is None:
        graph, store = _file_admin_graph()
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
        graph.add(product)
        graph.save(store)
        return product
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


async def update_strategy(session: AsyncSession | None, strategy: Strategy, data: StrategyFormData) -> Strategy:
    if strategy.status is not StrategyStatus.DRAFT:
        raise ValueError("Редактировать можно только draft-стратегии.")
    strategy.author_id = data.author_id
    strategy.slug = data.slug
    strategy.title = data.title
    strategy.short_description = data.short_description
    strategy.full_description = data.full_description
    strategy.risk_level = data.risk_level
    strategy.status = data.status
    strategy.min_capital_rub = data.min_capital_rub
    strategy.is_public = data.is_public
    if session is None:
        graph, store = _file_admin_graph()
        persisted = graph.strategies.get(strategy.id)
        if persisted is None:
            raise ValueError("Strategy not found")
        persisted.author_id = strategy.author_id
        persisted.slug = strategy.slug
        persisted.title = strategy.title
        persisted.short_description = strategy.short_description
        persisted.full_description = strategy.full_description
        persisted.risk_level = strategy.risk_level
        persisted.status = strategy.status
        persisted.min_capital_rub = strategy.min_capital_rub
        persisted.is_public = strategy.is_public
        graph.save(store)
        return persisted
    await session.commit()
    await session.refresh(strategy)
    return strategy


async def update_product(
    session: AsyncSession | None, product: SubscriptionProduct, data: ProductFormData
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
    if session is None:
        graph, store = _file_admin_graph()
        persisted = graph.products.get(product.id)
        if persisted is None:
            raise ValueError("Product not found")
        persisted.product_type = product.product_type
        persisted.slug = product.slug
        persisted.title = product.title
        persisted.description = product.description
        persisted.strategy_id = product.strategy_id
        persisted.author_id = product.author_id
        persisted.bundle_id = product.bundle_id
        persisted.billing_period = product.billing_period
        persisted.price_rub = product.price_rub
        persisted.trial_days = product.trial_days
        persisted.is_active = product.is_active
        persisted.autorenew_allowed = product.autorenew_allowed
        graph.save(store)
        return persisted
    await session.commit()
    await session.refresh(product)
    return product


async def confirm_payment_and_activate_subscription(
    session: AsyncSession | None,
    payment: Payment,
    *,
    confirmed_at: datetime | None = None,
) -> tuple[Payment, list[Subscription]]:
    if session is None:
        graph, store = _file_admin_graph()
        payment = graph.payments.get(payment.id)
        if payment is None:
            raise ValueError("Payment not found")
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
        await sync_promo_redemption_counter(None, payment.promo_code, store=store)
        graph.save(store)
        return payment, payment.subscriptions

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
    await sync_promo_redemption_counter(session, payment.promo_code)
    await session.refresh(payment)
    for subscription in payment.subscriptions:
        await session.refresh(subscription)
    return payment, payment.subscriptions


async def apply_manual_discount_to_payment(
    session: AsyncSession | None,
    payment: Payment,
    *,
    discount_rub: int,
) -> Payment:
    if payment.status not in {PaymentStatus.CREATED, PaymentStatus.PENDING}:
        raise ValueError("Ручную скидку можно применять только к payment в статусах created или pending")
    if payment.provider.value == "tbank":
        raise ValueError("Для T-Bank ручную скидку меняйте до создания checkout, а не на готовом платеже")
    if discount_rub < 0:
        raise ValueError("Скидка не может быть отрицательной")

    max_discount = max(0, payment.amount_rub - payment.discount_rub)
    if discount_rub > max_discount:
        raise ValueError("Ручная скидка превышает допустимый остаток суммы")

    if session is None:
        graph, store = _file_admin_graph()
        payment = graph.payments.get(payment.id)
        if payment is None:
            raise ValueError("Payment not found")
        for subscription in payment.subscriptions:
            subscription.manual_discount_rub = discount_rub
        payload = dict(payment.provider_payload or {})
        payload["manual_discount_rub"] = discount_rub
        payment.provider_payload = payload
        payment.final_amount_rub = max(0, payment.amount_rub - payment.discount_rub - discount_rub)
        graph.save(store)
        return payment

    for subscription in payment.subscriptions:
        subscription.manual_discount_rub = discount_rub
    payload = dict(payment.provider_payload or {})
    payload["manual_discount_rub"] = discount_rub
    payment.provider_payload = payload
    payment.final_amount_rub = max(0, payment.amount_rub - payment.discount_rub - discount_rub)
    await session.commit()
    await session.refresh(payment)
    return payment


async def set_subscription_autorenew_admin(
    session: AsyncSession | None,
    subscription: Subscription,
    *,
    enabled: bool,
) -> Subscription:
    if subscription.status in {SubscriptionStatus.CANCELLED, SubscriptionStatus.BLOCKED, SubscriptionStatus.EXPIRED}:
        raise ValueError("Для terminal subscriptions изменение автопродления недоступно.")

    if session is None:
        graph, store = _file_admin_graph()
        persisted = graph.subscriptions.get(subscription.id)
        if persisted is None:
            raise ValueError("Subscription not found")
        persisted.autorenew_enabled = enabled
        graph.save(store)
        return persisted

    subscription.autorenew_enabled = enabled
    await session.commit()
    await session.refresh(subscription)
    return subscription


async def cancel_subscription_admin(
    session: AsyncSession | None,
    subscription: Subscription,
    *,
    cancelled_at: datetime | None = None,
) -> Subscription:
    if subscription.status in {SubscriptionStatus.CANCELLED, SubscriptionStatus.BLOCKED, SubscriptionStatus.EXPIRED}:
        raise ValueError("Terminal subscription нельзя отменить повторно.")

    timestamp = cancelled_at or datetime.now(timezone.utc)

    if session is None:
        graph, store = _file_admin_graph()
        persisted = graph.subscriptions.get(subscription.id)
        if persisted is None:
            raise ValueError("Subscription not found")
        persisted.status = SubscriptionStatus.CANCELLED
        persisted.autorenew_enabled = False
        if persisted.end_at is None or persisted.end_at > timestamp:
            persisted.end_at = timestamp
        if persisted.payment is not None and persisted.payment.status is PaymentStatus.PENDING:
            persisted.payment.status = PaymentStatus.CANCELLED
        graph.save(store)
        return persisted

    subscription.status = SubscriptionStatus.CANCELLED
    subscription.autorenew_enabled = False
    if subscription.end_at is None or subscription.end_at > timestamp:
        subscription.end_at = timestamp
    if subscription.payment is not None and subscription.payment.status is PaymentStatus.PENDING:
        subscription.payment.status = PaymentStatus.CANCELLED
    await session.commit()
    await session.refresh(subscription)
    return subscription


async def _count_query(session: AsyncSession, query: Any) -> int:
    result = await session.execute(query)
    return int(result.scalar_one() or 0)


def _filter_admin_subscriptions(
    items: list[Subscription],
    query_text: str | None,
) -> list[Subscription]:
    normalized = (query_text or "").strip().lower()
    if not normalized:
        return items
    return [item for item in items if _subscription_matches_query(item, normalized)]


def _subscription_matches_query(subscription: Subscription, normalized: str) -> bool:
    product = subscription.product
    user = subscription.user
    parts = [
        subscription.id,
        subscription.status.value,
        user.full_name if user is not None else None,
        user.email if user is not None else None,
        user.username if user is not None else None,
        product.title if product is not None else None,
        product.slug if product is not None else None,
        product.strategy.title if product is not None and product.strategy is not None else None,
        product.strategy.slug if product is not None and product.strategy is not None else None,
        product.author.display_name if product is not None and product.author is not None else None,
        product.author.slug if product is not None and product.author is not None else None,
        product.bundle.title if product is not None and product.bundle is not None else None,
        product.bundle.slug if product is not None and product.bundle is not None else None,
        subscription.lead_source.name if subscription.lead_source is not None else None,
    ]
    haystack = " ".join(part.strip().lower() for part in parts if part)
    return normalized in haystack


def _slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")[:120]


def _staff_role_slugs(user: User) -> set[RoleSlug]:
    return {item.slug for item in getattr(user, "roles", []) if item.slug in {RoleSlug.ADMIN, RoleSlug.AUTHOR, RoleSlug.MODERATOR}}


def _is_staff_user(user: User) -> bool:
    return bool(_staff_role_slugs(user))


def _matches_staff_role_filter(user: User, role_filter: str) -> bool:
    role_slugs = _staff_role_slugs(user)
    if role_filter == "all":
        return True
    if role_filter == "multi-role":
        return len(role_slugs) > 1
    try:
        target_role = RoleSlug(role_filter)
    except ValueError:
        return True
    return target_role in role_slugs


def _staff_sort_key(user: User) -> tuple[str, str]:
    primary = (user.full_name or user.email or user.username or user.id).lower()
    secondary = (user.email or user.username or "").lower()
    return primary, secondary


def _normalize_role_objects(existing_roles: list[Role], *, graph: FileDatasetGraph) -> list[Role]:
    normalized: list[Role] = []
    seen: set[RoleSlug] = set()
    for item in existing_roles:
        if item.slug in seen:
            continue
        seen.add(item.slug)
        normalized.append(_ensure_graph_role(graph, item.slug))
    return normalized


def _validate_staff_uniqueness_file(
    graph: FileDatasetGraph,
    *,
    email: str,
    telegram_user_id: int | None,
    current_user_id: str,
) -> None:
    for item in graph.users.values():
        if item.id == current_user_id:
            continue
        if (item.email or "").lower() == email:
            raise ValueError("Пользователь с таким email уже существует.")
        if telegram_user_id is not None and item.telegram_user_id == telegram_user_id:
            raise ValueError("Пользователь с таким Telegram ID уже существует.")


async def _validate_staff_uniqueness_sql(
    session: AsyncSession,
    *,
    email: str,
    telegram_user_id: int | None,
    current_user_id: str,
) -> None:
    existing_user_by_email = await session.execute(
        select(User).where(func.lower(User.email) == email, User.id != current_user_id)
    )
    if existing_user_by_email.scalar_one_or_none() is not None:
        raise ValueError("Пользователь с таким email уже существует.")
    if telegram_user_id is not None:
        existing_user_by_tg = await session.execute(
            select(User).where(User.telegram_user_id == telegram_user_id, User.id != current_user_id)
        )
        if existing_user_by_tg.scalar_one_or_none() is not None:
            raise ValueError("Пользователь с таким Telegram ID уже существует.")


async def _replace_staff_roles_sql(session: AsyncSession, user: User, role_slugs: tuple[RoleSlug, ...]) -> None:
    await session.execute(delete(user_roles).where(user_roles.c.user_id == user.id))
    for role_slug in role_slugs:
        role = await _ensure_sql_role(session, role_slug)
        await session.execute(insert(user_roles).values(user_id=user.id, role_id=role.id))


def _build_default_staff_display_name(user: User) -> str:
    if user.author_profile is not None and user.author_profile.display_name:
        return user.author_profile.display_name.strip()
    if user.full_name:
        return user.full_name.strip()
    if user.email and "@" in user.email:
        return user.email.split("@", 1)[0].replace(".", " ").replace("_", " ").strip() or f"staff-{user.id[:8]}"
    if user.username:
        return user.username.strip()
    return f"staff-{user.id[:8]}"


async def create_admin_staff_user(session: AsyncSession | None, data: StaffCreateData) -> User:
    user = await _create_staff_user(session, data)
    await _deliver_staff_invite(session, user, role_slugs=data.role_slugs)
    return user


async def update_admin_staff_user(
    session: AsyncSession | None,
    *,
    actor_user_id: str,
    user_id: str,
    data: StaffUpdateData,
) -> User:
    normalized_display_name = data.display_name.strip()
    normalized_email = (data.email or "").strip().lower()
    role_slugs = tuple(dict.fromkeys(data.role_slugs))
    if not normalized_display_name:
        raise ValueError("Поле display_name обязательно.")
    if not normalized_email:
        raise ValueError("Поле email обязательно.")
    if not role_slugs:
        raise ValueError("Нужно указать хотя бы одну роль.")

    if session is None:
        graph, store = _file_admin_graph()
        user = graph.users.get(user_id)
        if user is None or not _is_staff_user(user):
            raise ValueError("Сотрудник не найден.")
        await _validate_admin_role_update_file(
            graph,
            actor_user_id=actor_user_id,
            user=user,
            role_slugs=role_slugs,
        )
        _validate_staff_uniqueness_file(graph, email=normalized_email, telegram_user_id=data.telegram_user_id, current_user_id=user.id)
        user.full_name = normalized_display_name
        user.email = normalized_email
        user.telegram_user_id = data.telegram_user_id or None
        user.roles = [_ensure_graph_role(graph, role_slug) for role_slug in role_slugs]
        if RoleSlug.AUTHOR in role_slugs:
            if user.author_profile is None:
                _create_file_author_profile(graph, user, normalized_display_name)
            else:
                user.author_profile.display_name = normalized_display_name
        elif user.author_profile is not None:
            user.author_profile.is_active = False
        graph.save(store)
        return user

    user = await _require_staff_user(session, user_id)
    await _validate_admin_role_update_sql(
        session,
        actor_user_id=actor_user_id,
        user=user,
        role_slugs=role_slugs,
    )
    await _validate_staff_uniqueness_sql(session, email=normalized_email, telegram_user_id=data.telegram_user_id, current_user_id=user.id)
    user.full_name = normalized_display_name
    user.email = normalized_email
    user.telegram_user_id = data.telegram_user_id or None
    await _replace_staff_roles_sql(session, user, role_slugs)
    if RoleSlug.AUTHOR in role_slugs:
        if user.author_profile is None:
            await _create_sql_author_profile(session, user, normalized_display_name)
        else:
            user.author_profile.display_name = normalized_display_name
    elif user.author_profile is not None:
        user.author_profile.is_active = False
    await session.commit()
    return await _require_staff_user(session, user.id)


async def set_admin_staff_user_status(
    session: AsyncSession | None,
    *,
    actor_user_id: str,
    user_id: str,
    is_active: bool,
) -> User:
    target_status = UserStatus.ACTIVE if is_active else UserStatus.INACTIVE
    if session is None:
        graph, store = _file_admin_graph()
        user = graph.users.get(user_id)
        actor = graph.users.get(actor_user_id)
        if user is None or not _is_staff_user(user):
            raise ValueError("Сотрудник не найден.")
        if user.status == target_status:
            return user
        if target_status == UserStatus.INACTIVE and RoleSlug.ADMIN in _staff_role_slugs(user) and user.status == UserStatus.ACTIVE:
            active_admins = _count_active_admins_file(graph)
            if active_admins <= 1:
                _raise_last_active_admin_deactivation_error(actor_user_id=actor_user_id, target_user_id=user.id)
        user.status = target_status
        graph.add(
            AuditEvent(
                actor_user=actor,
                actor_user_id=actor.id if actor is not None else None,
                entity_type="staff_user",
                entity_id=user.id,
                action="staff.activated" if is_active else "staff.deactivated",
                payload={"target_user_id": user.id, "status": user.status.value},
            )
        )
        graph.save(store)
        return user

    user = await _require_staff_user(session, user_id)
    if user.status == target_status:
        return user
    if target_status == UserStatus.INACTIVE and RoleSlug.ADMIN in _staff_role_slugs(user) and user.status == UserStatus.ACTIVE:
        active_admins = await _count_active_admins_sql(session)
        if active_admins <= 1:
            _raise_last_active_admin_deactivation_error(actor_user_id=actor_user_id, target_user_id=user.id)
    user.status = target_status
    session.add(
        AuditEvent(
            actor_user_id=actor_user_id,
            entity_type="staff_user",
            entity_id=user.id,
            action="staff.activated" if is_active else "staff.deactivated",
            payload={"target_user_id": user.id, "status": user.status.value},
        )
    )
    await session.commit()
    return await _require_staff_user(session, user.id)


async def grant_staff_role(
    session: AsyncSession | None,
    *,
    actor_user_id: str,
    target_user_id: str,
    role_slug: RoleSlug,
) -> User:
    if session is None:
        graph, store = _file_admin_graph()
        user = graph.users.get(target_user_id)
        actor = graph.users.get(actor_user_id)
        if user is None:
            raise ValueError("Сотрудник не найден.")
        if role_slug in _staff_role_slugs(user):
            raise ValueError("Роль уже назначена.")
        role = _ensure_graph_role(graph, role_slug)
        user.roles.append(role)
        if role_slug == RoleSlug.AUTHOR and user.author_profile is None:
            _create_file_author_profile(graph, user, _build_default_staff_display_name(user))
        if role_slug == RoleSlug.ADMIN:
            graph.add(
                AuditEvent(
                    actor_user=actor,
                    actor_user_id=actor.id if actor is not None else None,
                    entity_type="staff_user",
                    entity_id=user.id,
                    action="staff.admin_role_granted",
                    payload={"target_user_id": user.id, "role": role_slug.value},
                )
            )
        graph.save(store)
        return user

    user = await _get_staff_user_by_id(session, target_user_id)
    if user is None:
        raise ValueError("Сотрудник не найден.")
    if role_slug in _staff_role_slugs(user):
        raise ValueError("Роль уже назначена.")

    role = await _ensure_sql_role(session, role_slug)
    await session.execute(insert(user_roles).values(user_id=user.id, role_id=role.id))
    if role_slug == RoleSlug.AUTHOR and user.author_profile is None:
        await _create_sql_author_profile(session, user, _build_default_staff_display_name(user))
    if role_slug == RoleSlug.ADMIN:
        session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                entity_type="staff_user",
                entity_id=user.id,
                action="staff.admin_role_granted",
                payload={"target_user_id": user.id, "role": role_slug.value},
            )
        )
    await session.commit()
    return await _require_staff_user(session, user.id)


async def revoke_staff_role(
    session: AsyncSession | None,
    *,
    actor_user_id: str,
    target_user_id: str,
    role_slug: RoleSlug,
) -> User:
    if role_slug != RoleSlug.ADMIN:
        raise ValueError("Снятие этой роли пока не поддерживается.")

    if session is None:
        graph, store = _file_admin_graph()
        user = graph.users.get(target_user_id)
        actor = graph.users.get(actor_user_id)
        if user is None:
            raise ValueError("Сотрудник не найден.")
        if role_slug not in _staff_role_slugs(user):
            raise ValueError("Роль не назначена.")
        active_admins = _count_active_admins_file(graph)
        if user.status == UserStatus.ACTIVE and active_admins <= 1:
            _raise_last_active_admin_role_removal_error(actor_user_id=actor_user_id, target_user_id=user.id)
        user.roles = [item for item in user.roles if item.slug != role_slug]
        graph.add(
            AuditEvent(
                actor_user=actor,
                actor_user_id=actor.id if actor is not None else None,
                entity_type="staff_user",
                entity_id=user.id,
                action="staff.admin_role_revoked",
                payload={"target_user_id": user.id, "role": role_slug.value},
            )
        )
        graph.save(store)
        return user

    user = await _require_staff_user(session, target_user_id)
    if role_slug not in _staff_role_slugs(user):
        raise ValueError("Роль не назначена.")
    active_admins = await _count_active_admins_sql(session)
    if user.status == UserStatus.ACTIVE and active_admins <= 1:
        _raise_last_active_admin_role_removal_error(actor_user_id=actor_user_id, target_user_id=user.id)

    role = await _ensure_sql_role(session, role_slug)
    await session.execute(delete(user_roles).where(user_roles.c.user_id == user.id, user_roles.c.role_id == role.id))
    session.add(
        AuditEvent(
            actor_user_id=actor_user_id,
            entity_type="staff_user",
            entity_id=user.id,
            action="staff.admin_role_revoked",
            payload={"target_user_id": user.id, "role": role_slug.value},
        )
    )
    await session.commit()
    return await _require_staff_user(session, user.id)


async def _validate_admin_role_update_file(
    graph: FileDatasetGraph,
    *,
    actor_user_id: str,
    user: User,
    role_slugs: tuple[RoleSlug, ...],
) -> None:
    existing_roles = _staff_role_slugs(user)
    if RoleSlug.ADMIN not in existing_roles or RoleSlug.ADMIN in role_slugs or user.status != UserStatus.ACTIVE:
        return
    active_admins = _count_active_admins_file(graph)
    if active_admins <= 1:
        _raise_last_active_admin_role_removal_error(actor_user_id=actor_user_id, target_user_id=user.id)


async def _validate_admin_role_update_sql(
    session: AsyncSession,
    *,
    actor_user_id: str,
    user: User,
    role_slugs: tuple[RoleSlug, ...],
) -> None:
    existing_roles = _staff_role_slugs(user)
    if RoleSlug.ADMIN not in existing_roles or RoleSlug.ADMIN in role_slugs or user.status != UserStatus.ACTIVE:
        return
    active_admins = await _count_active_admins_sql(session)
    if active_admins <= 1:
        _raise_last_active_admin_role_removal_error(actor_user_id=actor_user_id, target_user_id=user.id)


async def _create_staff_user(session: AsyncSession | None, data: StaffCreateData) -> User:
    normalized_display_name = data.display_name.strip()
    normalized_email = (data.email or "").strip().lower()
    role_slugs = tuple(dict.fromkeys(data.role_slugs))
    if not normalized_display_name:
        raise ValueError("Поле display_name обязательно.")
    if not normalized_email:
        raise ValueError("Поле email обязательно.")
    if not role_slugs:
        raise ValueError("Нужно указать хотя бы одну роль.")

    if session is None:
        graph, store = _file_admin_graph()
        # Z1: Check for ghost user (exists but has no staff roles) — recover instead of error
        existing_user = next(
            (item for item in graph.users.values() if (item.email or "").lower() == normalized_email),
            None,
        )
        if existing_user is not None:
            if _is_staff_user(existing_user):
                raise ValueError("Пользователь с таким email уже существует.")
            # Recovery: update existing user with no staff roles
            existing_user.full_name = normalized_display_name
            existing_user.telegram_user_id = data.telegram_user_id or None
            existing_user.roles = [_ensure_graph_role(graph, role_slug) for role_slug in role_slugs]
            if RoleSlug.AUTHOR in role_slugs and not existing_user.author_profile:
                _create_file_author_profile(graph, existing_user, normalized_display_name)
            graph.save(store)
            return existing_user
        if data.telegram_user_id is not None and any(item.telegram_user_id == data.telegram_user_id for item in graph.users.values()):
            raise ValueError("Пользователь с таким Telegram ID уже существует.")

        user = User(
            email=normalized_email,
            telegram_user_id=data.telegram_user_id or None,
            full_name=normalized_display_name,
            status=UserStatus.INVITED,
            invite_token_version=1,
            invite_delivery_status=None,
        )
        user.roles = [_ensure_graph_role(graph, role_slug) for role_slug in role_slugs]
        graph.add(user)
        if RoleSlug.AUTHOR in role_slugs:
            _create_file_author_profile(graph, user, normalized_display_name)
        graph.save(store)
        return user

    # Z1: Check for ghost user (exists but has no staff roles) — recover instead of error
    existing_user_by_email = await session.execute(
        select(User).options(selectinload(User.roles)).where(func.lower(User.email) == normalized_email)
    )
    existing_user = existing_user_by_email.scalar_one_or_none()
    if existing_user is not None:
        if _is_staff_user(existing_user):
            raise ValueError("Пользователь с таким email уже существует.")
        # Recovery: update existing user with no staff roles
        existing_user.full_name = normalized_display_name
        existing_user.telegram_user_id = data.telegram_user_id or None
        # Clear old roles
        await session.execute(delete(user_roles).where(user_roles.c.user_id == existing_user.id))
        # Add new roles
        for role_slug in role_slugs:
            role = await _ensure_sql_role(session, role_slug)
            await session.execute(insert(user_roles).values(user_id=existing_user.id, role_id=role.id))
        if RoleSlug.AUTHOR in role_slugs:
            # Create author profile if not exists
            author_result = await session.execute(
                select(AuthorProfile).where(AuthorProfile.user_id == existing_user.id)
            )
            if author_result.scalar_one_or_none() is None:
                await _create_sql_author_profile(session, existing_user, normalized_display_name)
        await session.commit()
        return await _require_staff_user(session, existing_user.id)
    if data.telegram_user_id is not None:
        existing_user_by_tg = await session.execute(select(User).where(User.telegram_user_id == data.telegram_user_id))
        if existing_user_by_tg.scalar_one_or_none() is not None:
            raise ValueError("Пользователь с таким Telegram ID уже существует.")

    try:
        user = User(
            email=normalized_email,
            telegram_user_id=data.telegram_user_id or None,
            full_name=normalized_display_name,
            status=UserStatus.INVITED,
            invite_token_version=1,
            invite_delivery_status=None,
        )
        session.add(user)
        await session.flush()
        for role_slug in role_slugs:
            role = await _ensure_sql_role(session, role_slug)
            await session.execute(insert(user_roles).values(user_id=user.id, role_id=role.id))
        if RoleSlug.AUTHOR in role_slugs:
            await _create_sql_author_profile(session, user, normalized_display_name)
        await session.commit()
        return await _require_staff_user(session, user.id)
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError("Не удалось создать сотрудника из-за конфликта уникальности.") from exc


def _ensure_graph_role(graph: FileDatasetGraph, role_slug: RoleSlug) -> Role:
    role = next((item for item in graph.roles.values() if item.slug == role_slug), None)
    if role is not None:
        return role
    titles = {
        RoleSlug.ADMIN: "Администратор",
        RoleSlug.AUTHOR: "Автор",
        RoleSlug.MODERATOR: "Модератор",
    }
    role = Role(slug=role_slug, title=titles[role_slug])
    graph.add(role)
    return role


async def _ensure_sql_role(session: AsyncSession, role_slug: RoleSlug) -> Role:
    result = await session.execute(select(Role).where(Role.slug == role_slug))
    role = result.scalar_one_or_none()
    if role is not None:
        return role
    titles = {
        RoleSlug.ADMIN: "Администратор",
        RoleSlug.AUTHOR: "Автор",
        RoleSlug.MODERATOR: "Модератор",
    }
    role = Role(slug=role_slug, title=titles[role_slug])
    session.add(role)
    await session.flush()
    return role


def _create_file_author_profile(graph: FileDatasetGraph, user: User, display_name: str) -> AuthorProfile:
    slug = _slugify(display_name)
    if any(item.slug == slug for item in graph.authors.values()):
        import uuid

        slug = f"{slug}-{str(uuid.uuid4())[:8]}"
    profile = AuthorProfile(
        user_id=user.id,
        display_name=display_name,
        slug=slug,
        requires_moderation=False,
        is_active=True,
    )
    profile.user = user
    profile.watchlist_instruments = sorted(
        [item for item in graph.instruments.values() if item.is_active],
        key=lambda item: item.ticker.lower(),
    )
    graph.add(profile)
    for instrument in profile.watchlist_instruments:
        if profile not in instrument.watchlist_authors:
            instrument.watchlist_authors.append(profile)
    return profile


async def _create_sql_author_profile(session: AsyncSession, user: User, display_name: str) -> AuthorProfile:
    slug = _slugify(display_name)
    existing = await session.execute(select(AuthorProfile).where(AuthorProfile.slug == slug))
    if existing.scalar_one_or_none() is not None:
        import uuid

        slug = f"{slug}-{str(uuid.uuid4())[:8]}"
    profile = AuthorProfile(
        user_id=user.id,
        display_name=display_name,
        slug=slug,
        requires_moderation=False,
        is_active=True,
    )
    instruments_result = await session.execute(
        select(Instrument).where(Instrument.is_active.is_(True)).order_by(Instrument.ticker.asc())
    )
    profile.watchlist_instruments = list(instruments_result.scalars().all())
    session.add(profile)
    await session.flush()
    user.author_profile = profile
    return profile


async def _get_staff_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    result = await session.execute(
        select(User)
        .options(selectinload(User.roles), selectinload(User.author_profile))
        .where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def _require_staff_user(session: AsyncSession, user_id: str) -> User:
    user = await _get_staff_user_by_id(session, user_id)
    if user is None:
        raise ValueError("Сотрудник не найден.")
    return user


def _count_active_admins_file(graph: FileDatasetGraph) -> int:
    return sum(1 for user in graph.users.values() if user.status == UserStatus.ACTIVE and RoleSlug.ADMIN in _staff_role_slugs(user))


async def _count_active_admins_sql(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count(func.distinct(User.id)))
        .select_from(User)
        .join(user_roles, User.id == user_roles.c.user_id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(User.status == UserStatus.ACTIVE, Role.slug == RoleSlug.ADMIN)
    )
    return int(result.scalar_one())


def _raise_last_active_admin_role_removal_error(*, actor_user_id: str, target_user_id: str) -> None:
    if target_user_id == actor_user_id:
        raise ValueError("Нельзя снять у себя роль последнего активного администратора.")
    raise ValueError("Нельзя снять роль у последнего активного администратора.")


def _raise_last_active_admin_deactivation_error(*, actor_user_id: str, target_user_id: str) -> None:
    if target_user_id == actor_user_id:
        raise ValueError("Нельзя деактивировать себя как последнего активного администратора.")
    raise ValueError("Нельзя деактивировать последнего активного администратора.")


async def create_admin_author(
    session: AsyncSession | None,
    *,
    display_name: str,
    email: str | None,
    telegram_user_id: int | None,
) -> AuthorProfile:
    user = await _create_staff_user(
        session,
        StaffCreateData(
            display_name=display_name,
            email=email,
            telegram_user_id=telegram_user_id,
            role_slugs=(RoleSlug.AUTHOR,),
        ),
    )
    await _deliver_staff_invite(session, user, role_slugs=(RoleSlug.AUTHOR,))
    if user.author_profile is None:
        raise ValueError("Не удалось создать профиль автора.")
    return user.author_profile


async def update_admin_author(
    session: AsyncSession | None,
    *,
    actor_user_id: str,
    author_id: str,
    data: AdminAuthorUpdateData,
) -> AuthorProfile:
    normalized_display_name = data.display_name.strip()
    normalized_email = (data.email or "").strip().lower()
    role_slugs = tuple(dict.fromkeys(data.role_slugs or (RoleSlug.AUTHOR,)))
    if not normalized_display_name:
        raise ValueError("Поле display_name обязательно.")
    if not normalized_email:
        raise ValueError("Поле email обязательно.")
    if RoleSlug.AUTHOR not in role_slugs:
        raise ValueError("У автора должна оставаться роль author.")

    if session is None:
        graph, store = _file_admin_graph()
        profile = graph.authors.get(author_id)
        if profile is None or profile.user is None:
            raise ValueError("Автор не найден.")
        await _validate_admin_author_governance_file(
            graph,
            actor_user_id=actor_user_id,
            user=profile.user,
            role_slugs=role_slugs,
            is_active=data.is_active,
        )
        _validate_staff_uniqueness_file(graph, email=normalized_email, telegram_user_id=data.telegram_user_id, current_user_id=profile.user.id)
        profile.display_name = normalized_display_name
        profile.requires_moderation = data.requires_moderation
        profile.is_active = data.is_active
        profile.user.full_name = normalized_display_name
        profile.user.email = normalized_email
        profile.user.telegram_user_id = data.telegram_user_id or None
        profile.user.status = UserStatus.ACTIVE if data.is_active else UserStatus.INACTIVE
        profile.user.roles = [_ensure_graph_role(graph, role_slug) for role_slug in role_slugs]
        graph.save(store)
        return profile

    result = await session.execute(
        select(AuthorProfile).options(selectinload(AuthorProfile.user).selectinload(User.roles)).where(AuthorProfile.id == author_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None or profile.user is None:
        raise ValueError("Автор не найден.")
    await _validate_admin_author_governance_sql(
        session,
        actor_user_id=actor_user_id,
        user=profile.user,
        role_slugs=role_slugs,
        is_active=data.is_active,
    )
    await _validate_staff_uniqueness_sql(session, email=normalized_email, telegram_user_id=data.telegram_user_id, current_user_id=profile.user.id)
    profile.display_name = normalized_display_name
    profile.requires_moderation = data.requires_moderation
    profile.is_active = data.is_active
    profile.user.full_name = normalized_display_name
    profile.user.email = normalized_email
    profile.user.telegram_user_id = data.telegram_user_id or None
    profile.user.status = UserStatus.ACTIVE if data.is_active else UserStatus.INACTIVE
    await _replace_staff_roles_sql(session, profile.user, role_slugs)
    await session.commit()
    await session.refresh(profile)
    return profile


async def _validate_admin_author_governance_file(
    graph: FileDatasetGraph,
    *,
    actor_user_id: str,
    user: User,
    role_slugs: tuple[RoleSlug, ...],
    is_active: bool,
) -> None:
    await _validate_admin_role_update_file(
        graph,
        actor_user_id=actor_user_id,
        user=user,
        role_slugs=role_slugs,
    )
    if RoleSlug.ADMIN not in _staff_role_slugs(user) or user.status != UserStatus.ACTIVE or is_active:
        return
    active_admins = _count_active_admins_file(graph)
    if active_admins <= 1:
        _raise_last_active_admin_deactivation_error(actor_user_id=actor_user_id, target_user_id=user.id)


async def _validate_admin_author_governance_sql(
    session: AsyncSession,
    *,
    actor_user_id: str,
    user: User,
    role_slugs: tuple[RoleSlug, ...],
    is_active: bool,
) -> None:
    await _validate_admin_role_update_sql(
        session,
        actor_user_id=actor_user_id,
        user=user,
        role_slugs=role_slugs,
    )
    if RoleSlug.ADMIN not in _staff_role_slugs(user) or user.status != UserStatus.ACTIVE or is_active:
        return
    active_admins = await _count_active_admins_sql(session)
    if active_admins <= 1:
        _raise_last_active_admin_deactivation_error(actor_user_id=actor_user_id, target_user_id=user.id)


async def resend_staff_invite(
    session: AsyncSession | None,
    *,
    user_id: str,
) -> User:
    if session is None:
        graph, _store = _file_admin_graph()
        user = graph.users.get(user_id)
        if user is None:
            raise ValueError("Сотрудник не найден.")
    else:
        user = await _require_staff_user(session, user_id)

    role_slugs = tuple(sorted((role.slug for role in user.roles), key=lambda item: item.value))
    old_version = int(getattr(user, "invite_token_version", 1) or 1)
    user.invite_token_version = max(old_version + 1, 1)
    try:
        await _deliver_staff_invite(session, user, role_slugs=role_slugs, is_resend=True)
    except Exception:
        # Y1: Rollback version increment if email delivery failed.
        # Without this, the invite token would be invalidated but no new email sent.
        user.invite_token_version = old_version
        if session is None:
            graph, store = _file_admin_graph()
            persisted = graph.users.get(user.id)
            if persisted is not None:
                persisted.invite_token_version = old_version
                graph.save(store)
        else:
            await session.rollback()
        raise
    return user


async def _deliver_staff_invite(
    session: AsyncSession | None,
    user: User,
    *,
    role_slugs: tuple[RoleSlug, ...],
    is_resend: bool = False,
) -> None:
    # X3.1+X3.2: Use bot deep link as primary, web link as fallback
    invite_token = build_staff_invite_token(user)
    bot_link = build_staff_invite_bot_link(invite_token)
    invite_link = build_staff_invite_link(user)
    role_line = ", ".join(role.value for role in role_slugs)
    body = (
        f"Здравствуйте, {user.full_name or user.email or 'сотрудник'}!\n\n"
        "Для вас создан staff-доступ PitchCopyTrade.\n"
        f"Роли: {role_line}\n\n"
        f"Основной способ - нажмите кнопку в Telegram: {bot_link}\n"
        f"Альтернативно откройте через браузер: {invite_link}\n"
    )
    sent, error = await _send_email_message(
        to_email=user.email,
        subject="Приглашение в PitchCopyTrade staff",
        body=body,
    )
    user.invite_delivery_status = InviteDeliveryStatus.RESENT if sent and is_resend else (
        InviteDeliveryStatus.SENT if sent else InviteDeliveryStatus.FAILED
    )
    user.invite_delivery_error = None if sent else error
    user.invite_delivery_updated_at = datetime.now(timezone.utc)
    if session is None:
        graph, store = _file_admin_graph()
        persisted = graph.users.get(user.id)
        if persisted is not None:
            persisted.invite_token_version = user.invite_token_version
            persisted.invite_delivery_status = user.invite_delivery_status
            persisted.invite_delivery_error = user.invite_delivery_error
            persisted.invite_delivery_updated_at = user.invite_delivery_updated_at
            graph.add(
                AuditEvent(
                    entity_type="staff_invite",
                    entity_id=user.id,
                    action="staff.invite_sent",
                    payload={
                        "status": user.invite_delivery_status.value if user.invite_delivery_status is not None else None,
                        "error": user.invite_delivery_error,
                        "version": user.invite_token_version,
                    },
                )
            )
            graph.save(store)
        await _send_admin_oversight_email(None, user=user, role_slugs=role_slugs, sent=sent, error=error)
        return

    session.add(
        AuditEvent(
            entity_type="staff_invite",
            entity_id=user.id,
            action="staff.invite_sent",
            payload={
                "status": user.invite_delivery_status.value if user.invite_delivery_status is not None else None,
                "error": user.invite_delivery_error,
                "version": user.invite_token_version,
            },
        )
    )
    await session.commit()
    await _send_admin_oversight_email(session, user=user, role_slugs=role_slugs, sent=sent, error=error)


async def _send_admin_oversight_email(
    session: AsyncSession | None,
    *,
    user: User,
    role_slugs: tuple[RoleSlug, ...],
    sent: bool,
    error: str | None,
) -> None:
    if session is None:
        graph, _store = _file_admin_graph()
        recipients = [
            item.email
            for item in graph.users.values()
            if item.email and item.id != user.id and item.status == UserStatus.ACTIVE and RoleSlug.ADMIN in _staff_role_slugs(item)
        ]
    else:
        result = await session.execute(select(User).options(selectinload(User.roles)).where(User.status == UserStatus.ACTIVE))
        recipients = [
            item.email for item in result.scalars().all()
            if item.email and item.id != user.id and RoleSlug.ADMIN in _staff_role_slugs(item)
        ]
    if not recipients:
        return
    label = "автор" if role_slugs == (RoleSlug.AUTHOR,) else "администратор" if role_slugs == (RoleSlug.ADMIN,) else "сотрудник"
    summary = (
        f"Создан {label}: {user.full_name or user.email}\n"
        f"Роли: {', '.join(role.value for role in role_slugs)}\n"
        f"Приглашение: {'отправлено' if sent else f'ошибка ({error or 'unknown'})'}"
    )
    for email in recipients:
        await _send_email_message(
            to_email=email,
            subject="Контроль staff onboarding — PitchCopyTrade",
            body=summary,
        )


async def _send_email_message(*, to_email: str | None, subject: str, body: str) -> tuple[bool, str | None]:
    if not to_email:
        return False, "email not set"
    settings = get_settings()
    smtp_password = settings.notifications.smtp_password.get_secret_value().strip()
    if not smtp_password or smtp_password.startswith("__FILL_ME__"):
        return False, "smtp is not configured"
    try:
        import asyncio
        import aiosmtplib
        from email.message import EmailMessage

        message = EmailMessage()
        message["From"] = f"{settings.notifications.smtp_from_name} <{settings.notifications.smtp_from}>"
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)
        # Y2: Add timeout to prevent hanging on unresponsive SMTP servers
        await asyncio.wait_for(
            aiosmtplib.send(
                message,
                hostname=settings.notifications.smtp_host,
                port=settings.notifications.smtp_port,
                use_tls=settings.notifications.smtp_ssl,
                username=settings.notifications.smtp_user,
                password=smtp_password,
            ),
            timeout=10.0,
        )
        return True, None
    except asyncio.TimeoutError:
        logger.warning("SMTP timeout for %s", to_email)
        return False, "smtp timeout"
    except Exception as exc:
        logger.warning("email delivery failed for %s: %s", to_email, exc)
        return False, str(exc)


async def toggle_admin_author(session: AsyncSession | None, author_id: str) -> AuthorProfile:
    if session is None:
        graph, store = _file_admin_graph()
        profile = graph.authors.get(author_id)
        if profile is None:
            raise ValueError("Author not found")
        profile.is_active = not profile.is_active
        graph.save(store)
        return profile

    result = await session.execute(
        select(AuthorProfile).options(selectinload(AuthorProfile.user)).where(AuthorProfile.id == author_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise ValueError("Author not found")
    profile.is_active = not profile.is_active
    await session.commit()
    await session.refresh(profile)
    return profile


async def update_admin_author_permissions(
    session: AsyncSession | None,
    author_id: str,
    *,
    requires_moderation: bool,
) -> AuthorProfile:
    if session is None:
        graph, store = _file_admin_graph()
        profile = graph.authors.get(author_id)
        if profile is None:
            raise ValueError("Author not found")
        profile.requires_moderation = requires_moderation
        graph.save(store)
        return profile

    result = await session.execute(
        select(AuthorProfile).options(selectinload(AuthorProfile.user)).where(AuthorProfile.id == author_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise ValueError("Author not found")
    profile.requires_moderation = requires_moderation
    await session.commit()
    await session.refresh(profile)
    return profile


async def reseed_author_watchlists(session: AsyncSession | None) -> int:
    if session is None:
        graph, store = _file_admin_graph()
        instruments = [item for item in graph.instruments.values() if item.is_active]
        updated = 0
        for author in graph.authors.values():
            known_ids = {item.id for item in author.watchlist_instruments}
            missing = [item for item in instruments if item.id not in known_ids]
            if not missing:
                continue
            author.watchlist_instruments.extend(missing)
            for instrument in missing:
                if author not in instrument.watchlist_authors:
                    instrument.watchlist_authors.append(author)
            updated += 1
        if updated:
            graph.save(store)
        return updated

    instruments_result = await session.execute(select(Instrument).where(Instrument.is_active.is_(True)).order_by(Instrument.ticker.asc()))
    instruments = list(instruments_result.scalars().all())
    authors_result = await session.execute(
        select(AuthorProfile).options(selectinload(AuthorProfile.watchlist_instruments)).order_by(AuthorProfile.display_name.asc())
    )
    authors = list(authors_result.scalars().all())
    updated = 0
    for author in authors:
        known_ids = {item.id for item in author.watchlist_instruments}
        missing = [item for item in instruments if item.id not in known_ids]
        if not missing:
            continue
        author.watchlist_instruments.extend(missing)
        updated += 1
    if updated:
        await session.commit()
    return updated


async def get_admin_metrics(session: AsyncSession | None) -> dict:
    if session is None:
        graph, _store = _file_admin_graph()
        total_subscribers = sum(1 for u in graph.users.values() if not any(r.slug == RoleSlug.ADMIN for r in getattr(u, "roles", [])))
        active_subscriptions = sum(1 for s in graph.subscriptions.values() if s.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL])
        return {
            "total_subscribers": total_subscribers,
            "active_subscriptions": active_subscriptions,
            "new_this_week": 0,
            "strategy_stats": [],
        }

    from datetime import timedelta
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    total_subscribers = await _count_query(session, select(func.count(User.id)))
    active_subscriptions = await _count_query(
        session,
        select(func.count(Subscription.id)).where(
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL])
        ),
    )
    new_this_week = await _count_query(
        session,
        select(func.count(Subscription.id)).where(
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]),
            Subscription.created_at >= week_ago,
        ),
    )

    strategies_result = await session.execute(
        select(Strategy, func.count(Subscription.id).label("sub_count"))
        .outerjoin(SubscriptionProduct, SubscriptionProduct.strategy_id == Strategy.id)
        .outerjoin(Subscription, Subscription.product_id == SubscriptionProduct.id)
        .group_by(Strategy.id)
        .order_by(func.count(Subscription.id).desc())
    )
    strategy_stats = [
        {"title": row.Strategy.title, "sub_count": row.sub_count}
        for row in strategies_result
    ]

    return {
        "total_subscribers": total_subscribers,
        "active_subscriptions": active_subscriptions,
        "new_this_week": new_this_week,
        "strategy_stats": strategy_stats,
    }


async def get_admin_strategy_for_onepager(session: AsyncSession | None, strategy_id: str) -> Strategy | None:
    if session is None:
        graph, _store = _file_admin_graph()
        return graph.strategies.get(strategy_id)
    result = await session.execute(
        select(Strategy)
        .options(selectinload(Strategy.author))
        .where(Strategy.id == strategy_id)
    )
    return result.scalar_one_or_none()


async def save_strategy_onepager(session: AsyncSession | None, strategy_id: str, html_content: str) -> Strategy:
    if session is None:
        graph, store = _file_admin_graph()
        strategy = graph.strategies.get(strategy_id)
        if strategy is None:
            raise ValueError("Strategy not found")
        strategy.full_description = html_content
        graph.save(store)
        return strategy
    result = await session.execute(select(Strategy).where(Strategy.id == strategy_id))
    strategy = result.scalar_one_or_none()
    if strategy is None:
        raise ValueError("Strategy not found")
    strategy.full_description = html_content
    await session.commit()
    await session.refresh(strategy)
    return strategy
