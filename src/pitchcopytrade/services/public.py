from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from secrets import token_hex

from sqlalchemy.exc import IntegrityError

from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import LeadSource, Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import LegalDocument, Payment, PromoCode, Subscription
from pitchcopytrade.db.models.enums import (
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
from pitchcopytrade.billing import subscription_delta
from pitchcopytrade.services.compliance import bind_consents_to_payment, record_user_consent
from pitchcopytrade.services.promo import apply_promo_to_amount, sync_promo_redemption_counter, validate_promo_code_for_checkout


logger = logging.getLogger(__name__)

REQUIRED_CHECKOUT_DOCUMENT_TYPES = (LegalDocumentType.DISCLAIMER,)


@dataclass(slots=True)
class CheckoutRequest:
    full_name: str | None
    email: str | None
    timezone_name: str
    accepted_document_ids: list[str]
    lead_source_name: str | None = None
    promo_code_value: str | None = None
    ip_address: str | None = None
    telegram_user_id: int | None = None


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


@dataclass(slots=True, frozen=True)
class StrategyStory:
    thesis: str
    mechanics: str
    risk_rule: str
    commercial_cta_label: str


@dataclass(slots=True)
class CheckoutResult:
    user: User
    payment: Payment | None
    subscription: Subscription
    required_documents: list[LegalDocument]
    applied_promo_code: PromoCode | None = None
    payment_url: str | None = None
    provider_payment_id: str | None = None


class AlreadySubscribedError(Exception):
    def __init__(self, *, product_slug: str) -> None:
        super().__init__("Вы уже подписаны на эту стратегию")
        self.product_slug = product_slug


async def list_public_strategies(repository: PublicRepository) -> list[Strategy]:
    return await repository.list_public_strategies()


async def get_public_strategy_by_slug(repository: PublicRepository, slug: str) -> Strategy | None:
    return await repository.get_public_strategy_by_slug(slug)


def build_strategy_story(strategy: Strategy) -> StrategyStory:
    risk = _risk_level_label(strategy.risk_level).lower()
    risk_rule = f"Риск: {risk}."
    if strategy.min_capital_rub:
        risk_rule = f"{risk_rule} Минимальный капитал: {strategy.min_capital_rub} руб."
    return StrategyStory(
        thesis=strategy.short_description or "",
        mechanics=strategy.full_description or strategy.short_description or "",
        risk_rule=risk_rule,
        commercial_cta_label="Подписаться",
    )


def _risk_level_label(value: object) -> str:
    if hasattr(value, "value"):
        value = getattr(value, "value")
    labels = {
        "low": "Низкий риск",
        "medium": "Средний риск",
        "high": "Высокий риск",
    }
    return labels.get(str(value), str(value))


async def get_public_product(repository: PublicRepository, product_id: str) -> SubscriptionProduct | None:
    return await repository.get_public_product_by_ref(product_id)


async def get_public_product_by_ref(repository: PublicRepository, product_ref: str) -> SubscriptionProduct | None:
    return await repository.get_public_product_by_ref(product_ref)


async def get_public_product_by_slug(repository: PublicRepository, slug: str) -> SubscriptionProduct | None:
    return await repository.get_public_product_by_slug(slug)


async def list_active_checkout_documents(repository: PublicRepository) -> list[LegalDocument]:
    return await repository.list_active_checkout_documents()


async def find_user_by_email(repository: PublicRepository, email: str) -> User | None:
    return await repository.find_user_by_email(email)


async def upsert_telegram_subscriber(repository: PublicRepository, profile: TelegramSubscriberProfile) -> User:
    display_name = (profile.full_name or "").strip() or " ".join(
        part for part in [profile.first_name, profile.last_name] if part
    ).strip() or None
    normalized_email = (profile.email or "").strip().lower() or None
    user = await repository.get_user_by_telegram_id(profile.telegram_user_id)
    if user is not None:
        user.username = profile.username
        user.full_name = display_name
        if normalized_email is not None:
            user.email = normalized_email
        user.timezone = profile.timezone_name
        if user.status == UserStatus.INVITED:
            user.status = UserStatus.ACTIVE
        if user.consents is None:
            user.consents = []
        return user

    if normalized_email is not None:
        user = await repository.find_user_by_email(normalized_email)
        if user is not None and user.telegram_user_id is None:
            user.telegram_user_id = profile.telegram_user_id
            user.username = profile.username
            user.full_name = display_name
            user.timezone = profile.timezone_name
            if user.status == UserStatus.INVITED:
                user.status = UserStatus.ACTIVE
            if user.consents is None:
                user.consents = []
            logger.info(
                "Linked telegram_user_id=%s to existing user %s (email=%s)",
                profile.telegram_user_id,
                user.id,
                normalized_email,
            )
            return user
        if user is not None:
            user.username = profile.username
            user.full_name = display_name
            user.email = normalized_email
            user.timezone = profile.timezone_name
            if user.status == UserStatus.INVITED:
                user.status = UserStatus.ACTIVE
            if user.consents is None:
                user.consents = []
            return user

    if user is None:
        try:
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
            await repository.flush()
            return user
        except IntegrityError:
            await repository.rollback()
            logger.warning(
                "Race condition: telegram_user_id=%s was inserted concurrently, retrying lookup",
                profile.telegram_user_id,
            )
            user = await repository.get_user_by_telegram_id(profile.telegram_user_id)
            if user is None:
                raise
            user.username = profile.username
            user.full_name = display_name
            if normalized_email is not None:
                user.email = normalized_email
            user.timezone = profile.timezone_name
            if user.status == UserStatus.INVITED:
                user.status = UserStatus.ACTIVE
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
    required_documents = _visible_checkout_documents(required_documents)
    required_document_ids = {document.id for document in required_documents}
    accepted_document_ids = set(request.accepted_document_ids)

    if not required_document_ids.issubset(accepted_document_ids):
        raise ValueError("Нужно принять дисклеймер перед оплатой")
    promo_code = await _resolve_checkout_promo_code(
        repository,
        request.promo_code_value,
        now=timestamp,
    )
    pricing = apply_promo_to_amount(promo_code, amount_rub=product.price_rub) if promo_code is not None else None
    final_amount_rub = pricing.final_amount_rub if pricing is not None else product.price_rub
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
            telegram_user_id=request.telegram_user_id,
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
        if request.telegram_user_id is not None and user.telegram_user_id is None:
            user.telegram_user_id = request.telegram_user_id
            logger.info(
                "Public checkout: linked telegram_user_id=%s to user %s (email=%s)",
                request.telegram_user_id,
                user.id,
                user.email,
            )
        if user.consents is None:
            user.consents = []

    await _ensure_not_already_subscribed(repository, user=user, product=product)

    if final_amount_rub == 0:
        return await _create_free_checkout_records(
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
        pricing=pricing,
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
    required_documents = _visible_checkout_documents(required_documents)
    required_document_ids = {document.id for document in required_documents}
    if not required_document_ids.issubset(set(accepted_document_ids)):
        raise ValueError("Нужно принять дисклеймер перед оплатой")

    logger.info(
        "Mini App checkout binding: telegram_user_id=%s email=%s product=%s",
        profile.telegram_user_id,
        profile.email,
        product.slug,
    )
    user = await upsert_telegram_subscriber(repository, profile)
    if user.telegram_user_id is None:
        logger.error(
            "Mini App checkout invariant violated: profile_telegram_user_id=%s resolved_user_id=%s email=%s",
            profile.telegram_user_id,
            user.id,
            profile.email,
        )
        raise ValueError("Telegram ID не найден. Пожалуйста, откройте Mini App заново.")
    await _ensure_not_already_subscribed(repository, user=user, product=product)
    promo_code = await _resolve_checkout_promo_code(
        repository,
        promo_code_value,
        now=timestamp,
    )
    pricing = apply_promo_to_amount(promo_code, amount_rub=product.price_rub) if promo_code is not None else None
    final_amount_rub = pricing.final_amount_rub if pricing is not None else product.price_rub
    if final_amount_rub == 0:
        lead_source = await _resolve_checkout_lead_source(repository, profile.lead_source_name)
        if lead_source is not None and user.lead_source is None:
            user.lead_source = lead_source
            user.lead_source_id = lead_source.id
        return await _create_free_checkout_records(
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
    lead_source = await _resolve_checkout_lead_source(repository, profile.lead_source_name)
    if lead_source is not None and user.lead_source is None:
        user.lead_source = lead_source
        user.lead_source_id = lead_source.id
    if get_settings().payments.provider == "tbank":
        result = await _create_tbank_checkout_records(
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
        logger.info(
            "Mini App checkout persisted: product=%s user_id=%s telegram_user_id=%s payment_id=%s subscription_id=%s",
            product.slug,
            result.user.id,
            result.user.telegram_user_id,
            result.payment.id if result.payment is not None else None,
            result.subscription.id,
        )
        return result

    result = await _create_checkout_records(
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
        pricing=pricing,
    )
    logger.info(
        "Mini App checkout persisted: product=%s user_id=%s telegram_user_id=%s payment_id=%s subscription_id=%s",
        product.slug,
        result.user.id,
        result.user.telegram_user_id,
        result.payment.id if result.payment is not None else None,
        result.subscription.id,
    )
    return result


def _visible_checkout_documents(documents: list[LegalDocument]) -> list[LegalDocument]:
    visible = [document for document in documents if document.document_type is LegalDocumentType.DISCLAIMER]
    if not visible:
        raise ValueError("Checkout недоступен: не опубликован дисклеймер")
    return visible


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
    pricing=None,
) -> CheckoutResult:
    if pricing is None and promo_code is not None:
        pricing = apply_promo_to_amount(promo_code, amount_rub=product.price_rub)
    payment = Payment(
        user=user,
        product=product,
        promo_code=promo_code,
        provider=PaymentProvider.STUB_MANUAL,
        status=PaymentStatus.PAID,
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
        confirmed_at=timestamp,
    )
    payment.consents = []
    repository.add(payment)

    await repository.flush()

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
    for consent in consents:
        repository.add(consent)

    subscription = Subscription(
        user=user,
        product=product,
        payment=payment,
        status=SubscriptionStatus.ACTIVE,
        lead_source=lead_source,
        autorenew_enabled=product.autorenew_allowed,
        is_trial=product.trial_days > 0,
        manual_discount_rub=0,
        applied_promo_code=promo_code,
        start_at=timestamp,
        end_at=timestamp + subscription_delta(product.duration_days),
    )
    repository.add(subscription)

    await repository.commit()
    await repository.refresh(product)
    await repository.refresh(payment)
    await repository.refresh(subscription)
    await _sync_promo_redemption_counter(repository, promo_code)
    return CheckoutResult(
        user=user,
        payment=payment,
        subscription=subscription,
        required_documents=required_documents,
        applied_promo_code=promo_code,
    )


async def _create_free_checkout_records(
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
    subscription = Subscription(
        user=user,
        product=product,
        payment=None,
        status=SubscriptionStatus.ACTIVE,
        lead_source=lead_source,
        autorenew_enabled=product.autorenew_allowed,
        is_trial=product.trial_days > 0,
        manual_discount_rub=0,
        applied_promo_code=promo_code,
        start_at=timestamp,
        end_at=timestamp + subscription_delta(product.duration_days),
    )
    repository.add(subscription)

    await repository.flush()

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
    for consent in consents:
        repository.add(consent)

    await repository.commit()
    await repository.refresh(product)
    await repository.refresh(subscription)
    await _sync_promo_redemption_counter(repository, promo_code)
    return CheckoutResult(
        user=user,
        payment=None,
        subscription=subscription,
        required_documents=required_documents,
        applied_promo_code=promo_code,
    )


async def _sync_promo_redemption_counter(repository: PublicRepository, promo_code: PromoCode | None) -> None:
    if promo_code is None:
        return
    if not hasattr(repository, "session") and not hasattr(repository, "store"):
        return
    session = getattr(repository, "session", None)
    store = getattr(repository, "store", None)
    await sync_promo_redemption_counter(session, promo_code, store=store)


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
        success_url=f"{settings.app.base_url}/checkout/{product.slug}",
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

    await repository.flush()

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
    for consent in consents:
        repository.add(consent)

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
        end_at=timestamp + subscription_delta(product.duration_days),
    )
    repository.add(subscription)

    await repository.commit()
    await repository.refresh(product)
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


def _build_stub_reference(slug: str) -> str:
    return f"MANUAL-{slug.upper()}-{token_hex(4).upper()}"


async def _ensure_not_already_subscribed(
    repository: PublicRepository,
    *,
    user: User,
    product: SubscriptionProduct,
) -> None:
    if not user.id:
        return
    existing = await repository.get_active_subscription_for_product(user.id, product.id)
    if existing is not None:
        raise AlreadySubscribedError(product_slug=product.slug)
