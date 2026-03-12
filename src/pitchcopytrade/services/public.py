from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from secrets import token_hex

from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import LeadSource, Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import LegalDocument, Payment, PromoCode, Subscription
from pitchcopytrade.db.models.enums import (
    BillingPeriod,
    LegalDocumentType,
    PaymentProvider,
    PaymentStatus,
    StrategyStatus,
    SubscriptionStatus,
    UserStatus,
    LeadSourceType,
)
from pitchcopytrade.payments.tbank import TBankAcquiringClient
from pitchcopytrade.repositories.contracts import PublicRepository
from pitchcopytrade.services.compliance import bind_consents_to_payment, record_user_consent
from pitchcopytrade.services.promo import apply_promo_to_amount, validate_promo_code_for_checkout


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
    promo_code_value: str | None = None
    ip_address: str | None = None


@dataclass(slots=True)
class TelegramSubscriberProfile:
    telegram_user_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    full_name: str | None = None
    email: str | None = None
    timezone_name: str = "Europe/Moscow"
    lead_source_name: str | None = None


@dataclass(slots=True)
class CheckoutResult:
    user: User
    payment: Payment
    subscription: Subscription
    required_documents: list[LegalDocument]
    applied_promo_code: PromoCode | None = None
    payment_url: str | None = None
    provider_payment_id: str | None = None


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
    display_name = (profile.full_name or "").strip() or " ".join(
        part for part in [profile.first_name, profile.last_name] if part
    ).strip() or None
    normalized_email = (profile.email or "").strip().lower() or None
    if user is None:
        user = User(
            telegram_user_id=profile.telegram_user_id,
            username=profile.username,
            full_name=display_name,
            email=normalized_email,
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
    if normalized_email is not None:
        user.email = normalized_email
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
    promo_code = await _resolve_checkout_promo_code(
        repository,
        request.promo_code_value,
        now=timestamp,
    )
    lead_source = await _resolve_checkout_lead_source(repository, request.lead_source_name)
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
            lead_source=lead_source,
        )
        user.consents = []
        user.payments = []
        user.subscriptions = []
        repository.add(user)
    else:
        user.full_name = (request.full_name or "").strip() or user.full_name
        user.timezone = request.timezone_name
        if lead_source is not None and user.lead_source is None:
            user.lead_source = lead_source
            user.lead_source_id = lead_source.id
        if user.consents is None:
            user.consents = []

    if get_settings().payments.provider == "tbank":
        return await _create_tbank_checkout_records(
            repository,
            user=user,
            product=product,
            lead_source=lead_source,
            lead_source_name=request.lead_source_name,
            promo_code=promo_code,
            ip_address=request.ip_address,
            source="public_checkout",
            required_documents=required_documents,
            timestamp=timestamp,
        )

    return await _create_checkout_records(
        repository,
        user=user,
        product=product,
        lead_source=lead_source,
        lead_source_name=request.lead_source_name,
        promo_code=promo_code,
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
    accepted_document_ids: list[str],
    promo_code_value: str | None = None,
    now: datetime | None = None,
) -> CheckoutResult:
    timestamp = now or datetime.now(timezone.utc)
    required_documents = await list_active_checkout_documents(repository)
    if len(required_documents) != len(REQUIRED_CHECKOUT_DOCUMENT_TYPES):
        raise ValueError("Checkout недоступен: не опубликован полный комплект обязательных документов")
    required_document_ids = {document.id for document in required_documents}
    if required_document_ids != set(accepted_document_ids):
        raise ValueError("Нужно принять все обязательные документы перед оплатой")

    user = await upsert_telegram_subscriber(repository, profile)
    promo_code = await _resolve_checkout_promo_code(
        repository,
        promo_code_value,
        now=timestamp,
    )
    lead_source = await _resolve_checkout_lead_source(repository, profile.lead_source_name)
    if lead_source is not None and user.lead_source is None:
        user.lead_source = lead_source
        user.lead_source_id = lead_source.id
    if get_settings().payments.provider == "tbank":
        return await _create_tbank_checkout_records(
            repository,
            user=user,
            product=product,
            lead_source=lead_source,
            lead_source_name=profile.lead_source_name,
            promo_code=promo_code,
            ip_address=None,
            source="telegram_checkout",
            required_documents=required_documents,
            timestamp=timestamp,
        )

    return await _create_checkout_records(
        repository,
        user=user,
        product=product,
        lead_source=lead_source,
        lead_source_name=profile.lead_source_name,
        promo_code=promo_code,
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
    lead_source: LeadSource | None,
    lead_source_name: str | None,
    promo_code: PromoCode | None,
    ip_address: str | None,
    source: str,
    required_documents: list[LegalDocument],
    timestamp: datetime,
) -> CheckoutResult:
    pricing = apply_promo_to_amount(promo_code, amount_rub=product.price_rub) if promo_code is not None else None
    payment = Payment(
        user=user,
        product=product,
        promo_code=promo_code,
        provider=PaymentProvider.STUB_MANUAL,
        status=PaymentStatus.PENDING,
        amount_rub=product.price_rub,
        discount_rub=pricing.discount_rub if pricing is not None else 0,
        final_amount_rub=pricing.final_amount_rub if pricing is not None else product.price_rub,
        currency="RUB",
        stub_reference=_build_stub_reference(product.slug),
        provider_payload={
            "flow": source,
            "lead_source_name": lead_source_name,
            "promo_code": promo_code.code if promo_code is not None else None,
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
        lead_source=lead_source,
        autorenew_enabled=product.autorenew_allowed,
        is_trial=product.trial_days > 0,
        manual_discount_rub=0,
        applied_promo_code=promo_code,
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
        applied_promo_code=promo_code,
    )


async def _create_tbank_checkout_records(
    repository: PublicRepository,
    *,
    user: User,
    product: SubscriptionProduct,
    lead_source: LeadSource | None,
    lead_source_name: str | None,
    promo_code: PromoCode | None,
    ip_address: str | None,
    source: str,
    required_documents: list[LegalDocument],
    timestamp: datetime,
) -> CheckoutResult:
    settings = get_settings()
    order_id = _build_stub_reference(product.slug)
    pricing = apply_promo_to_amount(promo_code, amount_rub=product.price_rub) if promo_code is not None else None
    client = TBankAcquiringClient(
        terminal_key=settings.payments.tinkoff_terminal_key.get_secret_value(),
        password=settings.payments.tinkoff_secret_key.get_secret_value(),
    )
    checkout_session = await client.create_sbp_checkout(
        order_id=order_id,
        amount_rub=pricing.final_amount_rub if pricing is not None else product.price_rub,
        description=product.title,
        success_url=f"{settings.app.base_url}/checkout/{product.id}",
    )

    payment = Payment(
        user=user,
        product=product,
        promo_code=promo_code,
        provider=PaymentProvider.TBANK,
        status=PaymentStatus.PENDING,
        amount_rub=product.price_rub,
        discount_rub=pricing.discount_rub if pricing is not None else 0,
        final_amount_rub=pricing.final_amount_rub if pricing is not None else product.price_rub,
        currency="RUB",
        external_id=checkout_session.payment_id,
        stub_reference=order_id,
        provider_payload={
            "flow": source,
            "lead_source_name": lead_source_name,
            "promo_code": promo_code.code if promo_code is not None else None,
            "provider_payment_id": checkout_session.payment_id,
            "payment_url": checkout_session.payment_url,
            "init": checkout_session.init_payload,
            "qr": checkout_session.qr_payload,
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
        lead_source=lead_source,
        autorenew_enabled=product.autorenew_allowed,
        is_trial=product.trial_days > 0,
        manual_discount_rub=0,
        applied_promo_code=promo_code,
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
        applied_promo_code=promo_code,
        payment_url=checkout_session.payment_url,
        provider_payment_id=checkout_session.payment_id,
    )


async def _resolve_checkout_promo_code(
    repository: PublicRepository,
    promo_code_value: str | None,
    *,
    now: datetime,
) -> PromoCode | None:
    normalized = (promo_code_value or "").strip().upper()
    if not normalized:
        return None
    promo_code = await repository.find_active_promo_by_code(normalized)
    if promo_code is None:
        raise ValueError("Промокод не найден")
    validate_promo_code_for_checkout(
        promo_code,
        paid_redemptions=promo_code.current_redemptions,
        now=now,
    )
    return promo_code


async def _resolve_checkout_lead_source(
    repository: PublicRepository,
    lead_source_name: str | None,
) -> LeadSource | None:
    normalized = (lead_source_name or "").strip()
    if not normalized:
        return None
    resolver = getattr(repository, "get_lead_source_by_name", None)
    lead_source = await resolver(normalized) if resolver is not None else None
    if lead_source is not None:
        return lead_source
    lead_source = LeadSource(
        name=normalized,
        source_type=_infer_lead_source_type(normalized),
    )
    repository.add(lead_source)
    return lead_source


def _infer_lead_source_type(name: str) -> LeadSourceType:
    normalized = name.strip().lower()
    if "ads" in normalized or "cpc" in normalized or "target" in normalized:
        return LeadSourceType.ADS
    if "blog" in normalized or "influ" in normalized:
        return LeadSourceType.BLOGGER
    if "organic" in normalized or "seo" in normalized:
        return LeadSourceType.ORGANIC
    if "ref" in normalized or "partner" in normalized or "telegram" in normalized:
        return LeadSourceType.REFERRAL
    return LeadSourceType.DIRECT


def _billing_delta(period: BillingPeriod) -> timedelta:
    if period is BillingPeriod.MONTH:
        return timedelta(days=30)
    if period is BillingPeriod.QUARTER:
        return timedelta(days=90)
    return timedelta(days=365)


def _build_stub_reference(slug: str) -> str:
    return f"MANUAL-{slug.upper()}-{token_hex(4).upper()}"
