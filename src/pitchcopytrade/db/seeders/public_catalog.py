from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import LeadSource, Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import LegalDocument, PromoCode
from pitchcopytrade.db.models.enums import LegalDocumentType, LeadSourceType, ProductType, RiskLevel, StrategyStatus, UserStatus

logger = logging.getLogger(__name__)

_SEED_TIMESTAMP = datetime(2026, 3, 11, tzinfo=timezone.utc)
_LEGAL_SEED_ROOT = Path(__file__).resolve().parents[4] / "storage" / "seed" / "blob" / "legal"

_AUTHOR_EMAIL = "author@example.com"
_AUTHOR_USERNAME = "author1"
_AUTHOR_FULL_NAME = "Author One"
_AUTHOR_DISPLAY_NAME = "Author One"
_AUTHOR_SLUG = "author-one"

_STRATEGY_SLUG = "momentum-ru"
_STRATEGY_TITLE = "Momentum RU"
_PRODUCT_SLUG = "momentum-ru-month"
_PRODUCT_TITLE = "Momentum RU"


async def seed_public_catalog(session: AsyncSession) -> int:
    created_strategy = False

    author_user = await _get_or_create_author_user(session)
    author_profile = await _get_or_create_author_profile(session, author_user)
    strategy = await _get_or_create_strategy(session, author_profile)
    created_strategy = strategy is not None
    if strategy is None:
        strategy = await _get_strategy_by_slug(session, _STRATEGY_SLUG)
        if strategy is None:
            raise RuntimeError("Public strategy seed failed unexpectedly")

    await _get_or_create_product(session, strategy)
    await _get_or_create_lead_source(session)
    await _get_or_create_promo_code(session)
    await _ensure_legal_documents(session)

    await session.commit()
    if created_strategy:
        logger.info("Public catalog seeded")
        return 1
    logger.info("Public catalog already present, ensuring dependent rows only")
    return 0


async def _get_or_create_author_user(session: AsyncSession) -> User:
    existing = await _scalar_one_or_none(
        session,
        select(User).where(User.email == _AUTHOR_EMAIL),
    )
    if existing is not None:
        return existing

    user = User(
        email=_AUTHOR_EMAIL,
        telegram_user_id=111,
        username=_AUTHOR_USERNAME,
        full_name=_AUTHOR_FULL_NAME,
        status=UserStatus.ACTIVE,
        timezone="Europe/Moscow",
    )
    session.add(user)
    return user


async def _get_or_create_author_profile(session: AsyncSession, author_user: User) -> AuthorProfile:
    existing = await _scalar_one_or_none(
        session,
        select(AuthorProfile).where(AuthorProfile.slug == _AUTHOR_SLUG),
    )
    if existing is not None:
        return existing

    profile = AuthorProfile(
        user=author_user,
        display_name=_AUTHOR_DISPLAY_NAME,
        slug=_AUTHOR_SLUG,
        bio="Автор демонстрационной стратегии.",
        requires_moderation=False,
        is_active=True,
    )
    session.add(profile)
    return profile


async def _get_or_create_strategy(session: AsyncSession, author_profile: AuthorProfile) -> Strategy | None:
    existing = await _scalar_one_or_none(
        session,
        select(Strategy).where(Strategy.slug == _STRATEGY_SLUG),
    )
    if existing is not None:
        return None

    strategy = Strategy(
        author=author_profile,
        slug=_STRATEGY_SLUG,
        title=_STRATEGY_TITLE,
        short_description="Краткосрочные идеи по ликвидным российским акциям.",
        full_description="Демонстрационная стратегия для локального db-mode сценария.",
        risk_level=RiskLevel.MEDIUM,
        status=StrategyStatus.PUBLISHED,
        min_capital_rub=150000,
        is_public=True,
    )
    session.add(strategy)
    return strategy


async def _get_strategy_by_slug(session: AsyncSession, slug: str) -> Strategy | None:
    return await _scalar_one_or_none(session, select(Strategy).where(Strategy.slug == slug))


async def _get_or_create_product(session: AsyncSession, strategy: Strategy) -> SubscriptionProduct:
    existing = await _scalar_one_or_none(
        session,
        select(SubscriptionProduct).where(SubscriptionProduct.slug == _PRODUCT_SLUG),
    )
    if existing is not None:
        return existing

    product = SubscriptionProduct(
        product_type=ProductType.STRATEGY,
        slug=_PRODUCT_SLUG,
        title=_PRODUCT_TITLE,
        description="Подписка на одну стратегию.",
        strategy=strategy,
        duration_days=30,
        price_rub=499,
        trial_days=7,
        is_active=True,
        autorenew_allowed=True,
    )
    session.add(product)
    return product


async def _get_or_create_lead_source(session: AsyncSession) -> LeadSource | None:
    existing = await _scalar_one_or_none(
        session,
        select(LeadSource).where(LeadSource.name == "Telegram Organic"),
    )
    if existing is not None:
        return existing

    lead_source = LeadSource(
        source_type=LeadSourceType.ORGANIC,
        name="Telegram Organic",
        ref_code="tg-organic",
        utm_source="telegram",
        utm_medium="organic",
    )
    session.add(lead_source)
    return lead_source


async def _get_or_create_promo_code(session: AsyncSession) -> PromoCode | None:
    existing = await _scalar_one_or_none(
        session,
        select(PromoCode).where(PromoCode.code == "WELCOME10"),
    )
    if existing is not None:
        return existing

    promo_code = PromoCode(
        code="WELCOME10",
        description="Welcome promo for local testing",
        discount_percent=10,
        discount_amount_rub=None,
        max_redemptions=100,
        current_redemptions=4,
        expires_at=datetime(2026, 4, 30, tzinfo=timezone.utc),
        is_active=True,
    )
    session.add(promo_code)
    return promo_code


async def _ensure_legal_documents(session: AsyncSession) -> int:
    created = 0
    for document_type, title, content_md in _legal_documents_payload():
        existing = await _scalar_one_or_none(
            session,
            select(LegalDocument).where(
                LegalDocument.document_type == document_type,
                LegalDocument.version == "v1",
            ),
        )
        if existing is not None:
            continue
        session.add(
            LegalDocument(
                document_type=document_type,
                version="v1",
                title=title,
                content_md=content_md,
                source_path=f"legal/{document_type.value}/v1.md",
                is_active=True,
                published_at=_SEED_TIMESTAMP,
            )
        )
        created += 1
    return created


def _legal_documents_payload() -> list[tuple[LegalDocumentType, str, str]]:
    return [
        (
            LegalDocumentType.DISCLAIMER,
            "Предупреждение о рисках",
            _read_seed_legal_markdown(LegalDocumentType.DISCLAIMER, "Черновик дисклеймера для локального тестового контура."),
        ),
        (
            LegalDocumentType.OFFER,
            "Публичная оферта",
            _read_seed_legal_markdown(LegalDocumentType.OFFER, "Черновик оферты для локального тестового контура."),
        ),
        (
            LegalDocumentType.PRIVACY_POLICY,
            "Политика конфиденциальности",
            _read_seed_legal_markdown(LegalDocumentType.PRIVACY_POLICY, "Черновик privacy policy для локального тестового контура."),
        ),
        (
            LegalDocumentType.PAYMENT_CONSENT,
            "Согласие на оплату",
            _read_seed_legal_markdown(LegalDocumentType.PAYMENT_CONSENT, "Черновик согласия на оплату для локального тестового контура."),
        ),
    ]


def _read_seed_legal_markdown(document_type: LegalDocumentType, fallback: str) -> str:
    path = _LEGAL_SEED_ROOT / document_type.value / "v1.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return fallback


async def _scalar_one_or_none(session: AsyncSession, statement):
    result = await session.execute(statement)
    return result.scalar_one_or_none()
