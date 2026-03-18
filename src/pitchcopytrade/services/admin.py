from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.accounts import AuthorProfile, Role, User
from pitchcopytrade.db.models.catalog import Bundle, Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import Payment, Subscription, UserConsent
from pitchcopytrade.db.models.content import Recommendation
from pitchcopytrade.db.models.enums import (
    BillingPeriod,
    PaymentStatus,
    ProductType,
    RiskLevel,
    RoleSlug,
    StrategyStatus,
    SubscriptionStatus,
    UserStatus,
)
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore
from pitchcopytrade.services.promo import sync_promo_redemption_counter


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


async def list_admin_authors(session: AsyncSession | None) -> list[AuthorProfile]:
    if session is None:
        graph, _store = _file_admin_graph()
        items = [item for item in graph.authors.values() if item.is_active]
        items.sort(key=lambda item: item.display_name.lower())
        return items
    query = (
        select(AuthorProfile)
        .options(selectinload(AuthorProfile.user))
        .where(AuthorProfile.is_active.is_(True))
        .order_by(AuthorProfile.display_name.asc())
    )
    result = await session.execute(query)
    return list(result.scalars().all())


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
    if payment.status is not PaymentStatus.PENDING:
        raise ValueError("Ручную скидку можно применять только к payment в статусе pending")
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


async def create_admin_author(
    session: AsyncSession | None,
    *,
    display_name: str,
    email: str | None,
    telegram_user_id: int | None,
) -> AuthorProfile:
    if session is None:
        raise NotImplementedError("create_admin_author not supported in file mode")

    author_role_result = await session.execute(select(Role).where(Role.slug == RoleSlug.AUTHOR))
    author_role = author_role_result.scalar_one_or_none()
    if author_role is None:
        author_role = Role(slug=RoleSlug.AUTHOR, title="Автор")
        session.add(author_role)
        await session.flush()

    user = User(
        email=email or None,
        telegram_user_id=telegram_user_id or None,
        full_name=display_name,
        status=UserStatus.ACTIVE,
    )
    session.add(user)
    await session.flush()

    user.roles.append(author_role)

    slug = _slugify(display_name)
    # Ensure unique slug
    existing = await session.execute(
        select(AuthorProfile).where(AuthorProfile.slug == slug)
    )
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
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


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
