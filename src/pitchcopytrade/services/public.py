from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from secrets import token_hex

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
    UserStatus,
)
from pitchcopytrade.repositories.contracts import PublicRepository
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


async def list_public_strategies(repository: PublicRepository) -> list[Strategy]:
    return await repository.list_public_strategies()


async def get_public_strategy_by_slug(repository: PublicRepository, slug: str) -> Strategy | None:
    return await repository.get_public_strategy_by_slug(slug)


async def get_public_product(repository: PublicRepository, product_id: str) -> SubscriptionProduct | None:
    return await repository.get_public_product(product_id)


async def get_public_product_by_slug(repository: PublicRepository, slug: str) -> SubscriptionProduct | None:
    return await repository.get_public_product_by_slug(slug)


async def list_active_checkout_documents(repository: PublicRepository) -> list[LegalDocument]:
    return await repository.list_active_checkout_documents()


async def find_user_by_email(repository: PublicRepository, email: str) -> User | None:
    return await repository.find_user_by_email(email)


async def upsert_telegram_subscriber(repository: PublicRepository, profile: TelegramSubscriberProfile) -> User:
    user = await repository.get_user_by_telegram_id(profile.telegram_user_id)
    display_name = " ".join(part for part in [profile.first_name, profile.last_name] if part).strip() or None
    if user is None:
        user = User(
            telegram_user_id=profile.telegram_user_id,
            username=profile.username,
            full_name=display_name,
            status=UserStatus.ACTIVE,
            timezone=profile.timezone_name,
        )
        user.consents = []
        user.payments = []
        user.subscriptions = []
        repository.add(user)
        return user

    user.username = profile.username
    user.full_name = display_name
    user.timezone = profile.timezone_name
    if user.consents is None:
        user.consents = []
    return user


async def create_stub_checkout(
    repository: PublicRepository,
    *,
    product: SubscriptionProduct,
    request: CheckoutRequest,
    now: datetime | None = None,
) -> CheckoutResult:
    timestamp = now or datetime.now(timezone.utc)
    required_documents = await list_active_checkout_documents(repository)
    if len(required_documents) != len(REQUIRED_CHECKOUT_DOCUMENT_TYPES):
        raise ValueError("Checkout недоступен: не опубликован полный комплект обязательных документов")
    required_document_ids = {document.id for document in required_documents}
    accepted_document_ids = set(request.accepted_document_ids)

    if required_document_ids != accepted_document_ids:
        raise ValueError("Нужно принять все обязательные документы перед оплатой")
    user = None
    normalized_email = (request.email or "").strip().lower() or None
    if normalized_email is not None:
        user = await find_user_by_email(repository, normalized_email)

    if user is None:
        user = User(
            email=normalized_email,
            full_name=(request.full_name or "").strip() or None,
            username=None,
            password_hash=None,
            status=UserStatus.ACTIVE,
            timezone=request.timezone_name,
        )
        user.consents = []
        user.payments = []
        user.subscriptions = []
        repository.add(user)
    else:
        user.full_name = (request.full_name or "").strip() or user.full_name
        user.timezone = request.timezone_name
        if user.consents is None:
            user.consents = []

    return await _create_checkout_records(
        repository,
        user=user,
        product=product,
        lead_source_name=request.lead_source_name,
        ip_address=request.ip_address,
        source="public_checkout",
        required_documents=required_documents,
        timestamp=timestamp,
    )


async def create_telegram_stub_checkout(
    repository: PublicRepository,
    *,
    product: SubscriptionProduct,
    profile: TelegramSubscriberProfile,
    now: datetime | None = None,
) -> CheckoutResult:
    timestamp = now or datetime.now(timezone.utc)
    required_documents = await list_active_checkout_documents(repository)
    if len(required_documents) != len(REQUIRED_CHECKOUT_DOCUMENT_TYPES):
        raise ValueError("Checkout недоступен: не опубликован полный комплект обязательных документов")

    user = await upsert_telegram_subscriber(repository, profile)
    return await _create_checkout_records(
        repository,
        user=user,
        product=product,
        lead_source_name=profile.lead_source_name,
        ip_address=None,
        source="telegram_checkout",
        required_documents=required_documents,
        timestamp=timestamp,
    )


async def _create_checkout_records(
    repository: PublicRepository,
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
    repository.add(payment)

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
    repository.add(subscription)

    await repository.commit()
    await repository.refresh(payment)
    await repository.refresh(subscription)
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
