from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from secrets import token_hex

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import LegalDocument, Payment, Subscription
from pitchcopytrade.db.models.enums import (
    BillingPeriod,
    LegalDocumentType,
    PaymentProvider,
    PaymentStatus,
    StrategyStatus,
    SubscriptionStatus,
)
from pitchcopytrade.services.compliance import bind_consents_to_payment, record_user_consent


REQUIRED_CHECKOUT_DOCUMENT_TYPES = (
    LegalDocumentType.DISCLAIMER,
    LegalDocumentType.OFFER,
    LegalDocumentType.PRIVACY_POLICY,
    LegalDocumentType.PAYMENT_CONSENT,
)


@dataclass(slots=True)
class CheckoutRequest:
    full_name: str | None
    email: str | None
    timezone_name: str
    accepted_document_ids: list[str]
    lead_source_name: str | None = None
    ip_address: str | None = None


@dataclass(slots=True)
class TelegramSubscriberProfile:
    telegram_user_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    timezone_name: str = "Europe/Moscow"
    lead_source_name: str | None = None


@dataclass(slots=True)
class CheckoutResult:
    user: User
    payment: Payment
    subscription: Subscription
    required_documents: list[LegalDocument]


async def list_public_strategies(session: AsyncSession) -> list[Strategy]:
    query = (
        select(Strategy)
        .options(
            selectinload(Strategy.author).selectinload(AuthorProfile.user),
            selectinload(Strategy.subscription_products),
        )
        .where(Strategy.is_public.is_(True), Strategy.status == StrategyStatus.PUBLISHED)
        .order_by(Strategy.created_at.desc(), Strategy.title.asc())
    )
    result = await session.execute(query)
    strategies = list(result.scalars().all())
    for strategy in strategies:
        strategy.subscription_products = [product for product in strategy.subscription_products if product.is_active]
    return strategies


async def get_public_strategy_by_slug(session: AsyncSession, slug: str) -> Strategy | None:
    query = (
        select(Strategy)
        .options(
            selectinload(Strategy.author).selectinload(AuthorProfile.user),
            selectinload(Strategy.subscription_products),
        )
        .where(
            Strategy.slug == slug,
            Strategy.is_public.is_(True),
            Strategy.status == StrategyStatus.PUBLISHED,
        )
    )
    result = await session.execute(query)
    strategy = result.scalar_one_or_none()
    if strategy is not None:
        strategy.subscription_products = [product for product in strategy.subscription_products if product.is_active]
    return strategy


async def get_public_product(session: AsyncSession, product_id: str) -> SubscriptionProduct | None:
    query = (
        select(SubscriptionProduct)
        .options(
            selectinload(SubscriptionProduct.strategy).selectinload(Strategy.author),
            selectinload(SubscriptionProduct.author).selectinload(AuthorProfile.user),
        )
        .where(SubscriptionProduct.id == product_id, SubscriptionProduct.is_active.is_(True))
    )
    result = await session.execute(query)
    product = result.scalar_one_or_none()
    if product is None:
        return None
    if (
        product.strategy is not None
        and (not product.strategy.is_public or product.strategy.status is not StrategyStatus.PUBLISHED)
    ):
        return None
    return product


async def get_public_product_by_slug(session: AsyncSession, slug: str) -> SubscriptionProduct | None:
    query = (
        select(SubscriptionProduct)
        .options(
            selectinload(SubscriptionProduct.strategy).selectinload(Strategy.author),
            selectinload(SubscriptionProduct.author).selectinload(AuthorProfile.user),
        )
        .where(SubscriptionProduct.slug == slug, SubscriptionProduct.is_active.is_(True))
    )
    result = await session.execute(query)
    product = result.scalar_one_or_none()
    if product is None:
        return None
    if (
        product.strategy is not None
        and (not product.strategy.is_public or product.strategy.status is not StrategyStatus.PUBLISHED)
    ):
        return None
    return product


async def list_active_checkout_documents(session: AsyncSession) -> list[LegalDocument]:
    query = (
        select(LegalDocument)
        .where(
            LegalDocument.is_active.is_(True),
            LegalDocument.document_type.in_(REQUIRED_CHECKOUT_DOCUMENT_TYPES),
        )
        .order_by(LegalDocument.document_type.asc(), LegalDocument.version.desc())
    )
    result = await session.execute(query)
    documents = list(result.scalars().all())
    by_type: dict[LegalDocumentType, LegalDocument] = {}
    for document in documents:
        by_type.setdefault(document.document_type, document)
    return [by_type[item] for item in REQUIRED_CHECKOUT_DOCUMENT_TYPES if item in by_type]


async def find_user_by_email(session: AsyncSession, email: str) -> User | None:
    query = select(User).options(selectinload(User.consents)).where(User.email == email)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def upsert_telegram_subscriber(session: AsyncSession, profile: TelegramSubscriberProfile) -> User:
    query = select(User).options(selectinload(User.consents)).where(User.telegram_user_id == profile.telegram_user_id)
    result = await session.execute(query)
    user = result.scalar_one_or_none()
    display_name = " ".join(part for part in [profile.first_name, profile.last_name] if part).strip() or None
    if user is None:
        user = User(
            telegram_user_id=profile.telegram_user_id,
            username=profile.username,
            full_name=display_name,
            timezone=profile.timezone_name,
        )
        user.consents = []
        user.payments = []
        user.subscriptions = []
        session.add(user)
        return user

    user.username = profile.username
    user.full_name = display_name
    user.timezone = profile.timezone_name
    if user.consents is None:
        user.consents = []
    return user


async def create_stub_checkout(
    session: AsyncSession,
    *,
    product: SubscriptionProduct,
    request: CheckoutRequest,
    now: datetime | None = None,
) -> CheckoutResult:
    timestamp = now or datetime.now(timezone.utc)
    required_documents = await list_active_checkout_documents(session)
    if len(required_documents) != len(REQUIRED_CHECKOUT_DOCUMENT_TYPES):
        raise ValueError("Checkout недоступен: не опубликован полный комплект обязательных документов")
    required_document_ids = {document.id for document in required_documents}
    accepted_document_ids = set(request.accepted_document_ids)

    if required_document_ids != accepted_document_ids:
        raise ValueError("Нужно принять все обязательные документы перед оплатой")
    user = None
    normalized_email = (request.email or "").strip().lower() or None
    if normalized_email is not None:
        user = await find_user_by_email(session, normalized_email)

    if user is None:
        user = User(
            email=normalized_email,
            full_name=(request.full_name or "").strip() or None,
            username=None,
            password_hash=None,
            timezone=request.timezone_name,
        )
        user.consents = []
        user.payments = []
        user.subscriptions = []
        session.add(user)
    else:
        user.full_name = (request.full_name or "").strip() or user.full_name
        user.timezone = request.timezone_name
        if user.consents is None:
            user.consents = []

    return await _create_checkout_records(
        session,
        user=user,
        product=product,
        lead_source_name=request.lead_source_name,
        ip_address=request.ip_address,
        source="public_checkout",
        required_documents=required_documents,
        timestamp=timestamp,
    )


async def create_telegram_stub_checkout(
    session: AsyncSession,
    *,
    product: SubscriptionProduct,
    profile: TelegramSubscriberProfile,
    now: datetime | None = None,
) -> CheckoutResult:
    timestamp = now or datetime.now(timezone.utc)
    required_documents = await list_active_checkout_documents(session)
    if len(required_documents) != len(REQUIRED_CHECKOUT_DOCUMENT_TYPES):
        raise ValueError("Checkout недоступен: не опубликован полный комплект обязательных документов")

    user = await upsert_telegram_subscriber(session, profile)
    return await _create_checkout_records(
        session,
        user=user,
        product=product,
        lead_source_name=profile.lead_source_name,
        ip_address=None,
        source="telegram_checkout",
        required_documents=required_documents,
        timestamp=timestamp,
    )


async def _create_checkout_records(
    session: AsyncSession,
    *,
    user: User,
    product: SubscriptionProduct,
    lead_source_name: str | None,
    ip_address: str | None,
    source: str,
    required_documents: list[LegalDocument],
    timestamp: datetime,
) -> CheckoutResult:
    payment = Payment(
        user=user,
        product=product,
        provider=PaymentProvider.STUB_MANUAL,
        status=PaymentStatus.PENDING,
        amount_rub=product.price_rub,
        discount_rub=0,
        final_amount_rub=product.price_rub,
        currency="RUB",
        stub_reference=_build_stub_reference(product.slug),
        provider_payload={
            "flow": source,
            "lead_source_name": lead_source_name,
        },
        expires_at=timestamp + timedelta(hours=24),
    )
    payment.consents = []
    session.add(payment)

    consents = [
        record_user_consent(
            user=user,
            document=document,
            source=source,
            payment=None,
            accepted_at=timestamp,
            ip_address=ip_address,
        )
        for document in required_documents
    ]
    bind_consents_to_payment(consents=consents, payment=payment)

    subscription = Subscription(
        user=user,
        product=product,
        payment=payment,
        status=SubscriptionStatus.PENDING,
        autorenew_enabled=product.autorenew_allowed,
        is_trial=product.trial_days > 0,
        manual_discount_rub=0,
        start_at=timestamp,
        end_at=timestamp + _billing_delta(product.billing_period),
    )
    session.add(subscription)

    await session.commit()
    await session.refresh(payment)
    await session.refresh(subscription)
    return CheckoutResult(
        user=user,
        payment=payment,
        subscription=subscription,
        required_documents=required_documents,
    )


def _billing_delta(period: BillingPeriod) -> timedelta:
    if period is BillingPeriod.MONTH:
        return timedelta(days=30)
    if period is BillingPeriod.QUARTER:
        return timedelta(days=90)
    return timedelta(days=365)


def _build_stub_reference(slug: str) -> str:
    return f"MANUAL-{slug.upper()}-{token_hex(4).upper()}"
