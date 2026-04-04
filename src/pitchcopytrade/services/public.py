from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import re
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
from pitchcopytrade.services.promo import apply_promo_to_amount, sync_promo_redemption_counter, validate_promo_code_for_checkout
from pitchcopytrade.services.subscriber import billing_period_label


logger = logging.getLogger(__name__)

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
class StrategyStorySection:
    title: str
    body: str


@dataclass(slots=True, frozen=True)
class StrategyStory:
    hero_summary: str
    market_scope: str
    holding_period_note: str
    entry_logic: str
    risk_rule: str
    instrument_examples: list[str]
    who_is_it_for: list[str]
    who_is_it_not_for: list[str]
    faq_items: list[StrategyStorySection]
    thesis: str
    mechanics: str
    tariffs: list[str]
    commercial_cta_label: str
    commercial_cta_detail: str


@dataclass(slots=True)
class CheckoutResult:
    user: User
    payment: Payment | None
    subscription: Subscription
    required_documents: list[LegalDocument]
    applied_promo_code: PromoCode | None = None
    payment_url: str | None = None
    provider_payment_id: str | None = None


async def list_public_strategies(repository: PublicRepository) -> list[Strategy]:
    return await repository.list_public_strategies()


async def get_public_strategy_by_slug(repository: PublicRepository, slug: str) -> Strategy | None:
    return await repository.get_public_strategy_by_slug(slug)


def build_strategy_story(strategy: Strategy) -> StrategyStory:
    sections = _parse_full_description_sections(strategy.full_description or "")
    hero_summary = _first_non_empty(
        sections.get("hero"),
        sections.get("summary"),
        sections.get("thesis"),
        strategy.short_description,
    )
    thesis = _first_non_empty(
        sections.get("thesis"),
        sections.get("market"),
        strategy.full_description,
        strategy.short_description,
    )
    market_scope = _first_non_empty(
        sections.get("market_scope"),
        sections.get("market"),
        _build_market_scope(strategy),
    )
    holding_period_note = _first_non_empty(
        sections.get("holding_period_note"),
        sections.get("horizon"),
        _build_holding_period_note(strategy),
    )
    entry_logic = _first_non_empty(
        sections.get("entry_logic"),
        sections.get("mechanics"),
        _build_entry_logic(strategy),
    )
    risk_rule = _first_non_empty(
        sections.get("risk_rule"),
        sections.get("risk"),
        _build_risk_rule(strategy),
    )
    instrument_examples = _collect_bullets(
        sections.get("instrument_examples")
        or sections.get("instruments")
        or sections.get("examples")
        or _build_instrument_examples(strategy)
    )
    who_is_it_for = _collect_bullets(
        sections.get("who_is_it_for")
        or sections.get("for")
        or _build_audience_points(strategy, positive=True)
    )
    who_is_it_not_for = _collect_bullets(
        sections.get("who_is_it_not_for")
        or sections.get("not_for")
        or _build_audience_points(strategy, positive=False)
    )
    faq_items = _build_faq_items(strategy, sections)
    tariffs = _build_tariff_lines(strategy)
    mechanics = _first_non_empty(
        sections.get("mechanics"),
        _build_mechanics(strategy, entry_logic=entry_logic, market_scope=market_scope),
    )
    return StrategyStory(
        hero_summary=hero_summary,
        market_scope=market_scope,
        holding_period_note=holding_period_note,
        entry_logic=entry_logic,
        risk_rule=risk_rule,
        instrument_examples=instrument_examples,
        who_is_it_for=who_is_it_for,
        who_is_it_not_for=who_is_it_not_for,
        faq_items=faq_items,
        thesis=thesis,
        mechanics=mechanics,
        tariffs=tariffs,
        commercial_cta_label="Подписаться",
        commercial_cta_detail="Откройте тариф и завершите оформление внутри того же Mini App.",
    )


def _parse_full_description_sections(text: str) -> dict[str, str]:
    if not text.strip():
        return {}
    sections: dict[str, list[str]] = {}
    current_key = "body"
    for line in text.splitlines():
        heading = _normalize_heading(line)
        if heading is not None:
            current_key = heading
            sections.setdefault(current_key, [])
            continue
        sections.setdefault(current_key, []).append(line)
    normalized: dict[str, str] = {}
    for key, lines in sections.items():
        body = "\n".join(lines).strip()
        if body:
            normalized[key] = body
    if "body" in normalized and len(normalized) == 1:
        normalized["thesis"] = normalized["body"]
    return normalized


def _normalize_heading(line: str) -> str | None:
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None
    stripped = stripped.lstrip("#").strip()
    if not stripped:
        return None
    key = re.sub(r"[^a-z0-9а-я]+", "_", stripped.lower()).strip("_")
    aliases = {
        "hero": "hero",
        "summary": "hero",
        "thesis": "thesis",
        "идея": "thesis",
        "market": "market",
        "market_scope": "market_scope",
        "scope": "market_scope",
        "holding_period": "horizon",
        "holding_period_note": "horizon",
        "horizon": "horizon",
        "entry_logic": "entry_logic",
        "mechanics": "mechanics",
        "mechanic": "mechanics",
        "risk": "risk",
        "risk_rule": "risk_rule",
        "instrument_examples": "instrument_examples",
        "instruments": "instrument_examples",
        "examples": "instrument_examples",
        "who_is_it_for": "who_is_it_for",
        "for": "who_is_it_for",
        "who_is_it_not_for": "who_is_it_not_for",
        "not_for": "who_is_it_not_for",
        "faq": "faq",
        "faq_items": "faq",
        "documents": "faq",
        "tariffs": "tariffs",
        "pricing": "tariffs",
    }
    return aliases.get(key)


def _first_non_empty(*values: str | None) -> str:
    for value in values:
        if value is not None:
            text = value.strip()
            if text:
                return text
    return ""


def _collect_bullets(value: str) -> list[str]:
    lines = [line.strip(" •-\t") for line in value.splitlines() if line.strip()]
    bullets = [line for line in lines if line]
    if bullets:
        return bullets
    return [value.strip()] if value.strip() else []


def _build_market_scope(strategy: Strategy) -> str:
    risk = _risk_level_label(strategy.risk_level)
    return f"Сценарий сфокусирован на российском рынке и подаётся как читаемый сценарий для уровня риска {risk.lower()}."


def _build_holding_period_note(strategy: Strategy) -> str:
    if strategy.subscription_products:
        labels = sorted({billing_period_label(product.billing_period) for product in strategy.subscription_products})
        if len(labels) == 1:
            return f"Горизонт поддержки привязан к тарифу: {labels[0].lower()}."
        return f"Горизонт поддержки варьируется по тарифам: {', '.join(label.lower() for label in labels)}."
    return "Горизонт уточняется в выбранном тарифе."


def _build_entry_logic(strategy: Strategy) -> str:
    return (
        strategy.short_description
        or f"Сценарий входа описан через логику {strategy.title} и раскрывается в полном описании."
    )


def _build_risk_rule(strategy: Strategy) -> str:
    risk = _risk_level_label(strategy.risk_level)
    min_capital = f"Минимальный капитал: {strategy.min_capital_rub} руб." if strategy.min_capital_rub else "Минимальный капитал в карточке пока не задан."
    # return f"Риск: {risk.lower()}. {min_capital} Коммерческая CTA завязана на тот же маршрут оплаты."
    return f"Риск: {risk.lower()}. {min_capital}."


def _build_instrument_examples(strategy: Strategy) -> str:
    return (
        "Конкретные инструменты раскрываются в рекомендациях и в детальном сценарии автора."
        if strategy.full_description
        else "Инструментальный набор раскрывается в рекомендациях и может дополняться по мере публикации новых сценариев."
    )


def _build_audience_points(strategy: Strategy, *, positive: bool) -> str:
    risk = _risk_level_label(strategy.risk_level).lower()
    if positive:
        return "\n".join(
            [
                f"Подходит тем, кому нужен структурный сценарий с риском уровня {risk}.",
                "Подходит тем, кто читает стратегию перед действием, а не покупает «тикер ради тикера».",
                "Подходит тем, кто готов открыть тариф и пройти checkout внутри Mini App.",
            ]
        )
    return "\n".join(
        [
            "Не подходит тем, кто ищет мгновенный результат без чтения сценария.",
            "Не подходит тем, кто не готов принимать риски рыночного сценария.",
            "Не подходит тем, кто хочет закрыть решение без просмотра деталей и тарифа.",
        ]
    )


def _build_faq_items(strategy: Strategy, sections: dict[str, str]) -> list[StrategyStorySection]:
    items = []
    if faq_text := sections.get("faq"):
        for part in re.split(r"\n{2,}", faq_text):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                question, answer = part.split(":", 1)
                items.append(StrategyStorySection(title=question.strip(), body=answer.strip()))
            else:
                items.append(StrategyStorySection(title="FAQ", body=part))
    if items:
        return items
    risk = _risk_level_label(strategy.risk_level).lower()
    return [
        StrategyStorySection(
            title="Сколько времени нужен сценарий?",
            body=_build_holding_period_note(strategy),
        ),
        StrategyStorySection(
            title="Где смотреть риск?",
            body=f"В карточке сразу виден риск уровня {risk} и минимальный капитал.",
        ),
        StrategyStorySection(
            title="Что происходит после выбора тарифа?",
            body="Пользователь открывает checkout, принимает документы и остаётся внутри того же Mini App.",
        ),
    ]


def _build_tariff_lines(strategy: Strategy) -> list[str]:
    tariffs: list[str] = []
    for product in strategy.subscription_products:
        period = billing_period_label(product.billing_period)
        parts = [product.title, f"{product.price_rub} руб", period]
        if product.trial_days:
            parts.append(f"{product.trial_days} дней trial")
        tariffs.append(" · ".join(parts))
    if tariffs:
        return tariffs
    return ["Тарифы появятся после публикации активных subscription products."]


def _build_mechanics(strategy: Strategy, *, entry_logic: str, market_scope: str) -> str:
    return (
        f"{entry_logic}\n\n{market_scope}\n\n"
        f"В полноценной карточке эта секция раскрывает механику сценария без длинной стены текста, "
        f"а детали сделки и коммерческая логика остаются связанными с выбранным тарифом."
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
            if user.consents is None:
                user.consents = []
            logger.info(
                "Linked telegram_user_id=%s to existing user %s (email=%s)",
                profile.telegram_user_id,
                user.id,
                normalized_email,
            )
            return user

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
    if len(required_documents) != len(REQUIRED_CHECKOUT_DOCUMENT_TYPES):
        raise ValueError("Checkout недоступен: не опубликован полный комплект обязательных документов")
    required_document_ids = {document.id for document in required_documents}
    if required_document_ids != set(accepted_document_ids):
        raise ValueError("Нужно принять все обязательные документы перед оплатой")

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
        end_at=timestamp + _billing_delta(product.billing_period),
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
        end_at=timestamp + _billing_delta(product.billing_period),
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
        end_at=timestamp + _billing_delta(product.billing_period),
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


def _billing_delta(period: BillingPeriod) -> timedelta:
    if period is BillingPeriod.MONTH:
        return timedelta(days=30)
    if period is BillingPeriod.QUARTER:
        return timedelta(days=90)
    return timedelta(days=365)


def _build_stub_reference(slug: str) -> str:
    return f"MANUAL-{slug.upper()}-{token_hex(4).upper()}"
