from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import LeadSource, Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import LegalDocument, Payment, PromoCode, Subscription, UserConsent
from pitchcopytrade.db.models.enums import LegalDocumentType, StrategyStatus, SubscriptionStatus
from pitchcopytrade.repositories.contracts import PublicRepository
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore

ACTIVE_SUBSCRIPTION_STATUSES = (
    SubscriptionStatus.ACTIVE,
    SubscriptionStatus.TRIAL,
)


class SqlAlchemyPublicRepository(PublicRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_public_strategies(self) -> list[Strategy]:
        query = (
            select(Strategy)
            .options(
                selectinload(Strategy.author).selectinload(AuthorProfile.user),
                selectinload(Strategy.subscription_products),
            )
            .where(Strategy.is_public.is_(True), Strategy.status == StrategyStatus.PUBLISHED)
            .order_by(Strategy.created_at.desc(), Strategy.title.asc())
        )
        result = await self.session.execute(query)
        strategies = list(result.scalars().all())
        for strategy in strategies:
            strategy.subscription_products = [product for product in strategy.subscription_products if product.is_active]
        return strategies

    async def get_public_strategy_by_slug(self, slug: str) -> Strategy | None:
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
        result = await self.session.execute(query)
        strategy = result.scalar_one_or_none()
        if strategy is not None:
            strategy.subscription_products = [product for product in strategy.subscription_products if product.is_active]
        return strategy

    async def get_public_product_by_ref(self, product_ref: str) -> SubscriptionProduct | None:
        normalized = (product_ref or "").strip()
        if not normalized:
            return None
        product = await self.get_public_product_by_slug(normalized)
        if product is not None:
            return product
        try:
            UUID(normalized)
        except ValueError:
            return None
        return await self.get_public_product(normalized)

    async def get_public_product(self, product_id: str) -> SubscriptionProduct | None:
        query = (
            select(SubscriptionProduct)
            .options(
                selectinload(SubscriptionProduct.strategy).selectinload(Strategy.author),
                selectinload(SubscriptionProduct.author).selectinload(AuthorProfile.user),
            )
            .where(SubscriptionProduct.id == product_id, SubscriptionProduct.is_active.is_(True))
        )
        result = await self.session.execute(query)
        product = result.scalar_one_or_none()
        if product is None:
            return None
        if (
            product.strategy is not None
            and (not product.strategy.is_public or product.strategy.status is not StrategyStatus.PUBLISHED)
        ):
            return None
        return product

    async def get_public_product_by_slug(self, slug: str) -> SubscriptionProduct | None:
        query = (
            select(SubscriptionProduct)
            .options(
                selectinload(SubscriptionProduct.strategy).selectinload(Strategy.author),
                selectinload(SubscriptionProduct.author).selectinload(AuthorProfile.user),
            )
            .where(SubscriptionProduct.slug == slug, SubscriptionProduct.is_active.is_(True))
        )
        result = await self.session.execute(query)
        product = result.scalar_one_or_none()
        if product is None:
            return None
        if (
            product.strategy is not None
            and (not product.strategy.is_public or product.strategy.status is not StrategyStatus.PUBLISHED)
        ):
            return None
        return product

    async def list_active_checkout_documents(self) -> list[LegalDocument]:
        query = (
            select(LegalDocument)
            .where(
                LegalDocument.is_active.is_(True),
                LegalDocument.document_type.in_(FilePublicRepository.REQUIRED_CHECKOUT_DOCUMENT_TYPES),
            )
            .order_by(LegalDocument.document_type.asc(), LegalDocument.version.desc())
        )
        result = await self.session.execute(query)
        documents = list(result.scalars().all())
        by_type: dict[LegalDocumentType, LegalDocument] = {}
        for document in documents:
            by_type.setdefault(document.document_type, document)
        return [by_type[item] for item in FilePublicRepository.REQUIRED_CHECKOUT_DOCUMENT_TYPES if item in by_type]

    async def find_active_promo_by_code(self, code: str) -> PromoCode | None:
        normalized = code.strip().upper()
        if not normalized:
            return None
        query = select(PromoCode).where(PromoCode.code == normalized)
        result = await self.session.execute(query)
        promo = result.scalar_one_or_none()
        if promo is None or not promo.is_active:
            return None
        return promo

    async def get_lead_source_by_name(self, name: str) -> LeadSource | None:
        normalized = name.strip()
        if not normalized:
            return None
        query = select(LeadSource).where(func.lower(LeadSource.name) == normalized.lower()).limit(1)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def find_user_by_email(self, email: str) -> User | None:
        query = select(User).options(selectinload(User.consents)).where(User.email == email)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> User | None:
        query = (
            select(User)
            .options(
                selectinload(User.consents),
                selectinload(User.payments).selectinload(Payment.product),
                selectinload(User.subscriptions).selectinload(Subscription.product),
                selectinload(User.subscriptions).selectinload(Subscription.applied_promo_code),
                selectinload(User.subscriptions).selectinload(Subscription.payment),
            )
            .where(User.telegram_user_id == telegram_user_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_user_payment(self, *, telegram_user_id: int, payment_id: str) -> Payment | None:
        user = await self.get_user_by_telegram_id(telegram_user_id)
        if user is None:
            return None
        return next((item for item in user.payments if item.id == payment_id), None)

    async def get_user_subscription(self, *, telegram_user_id: int, subscription_id: str) -> Subscription | None:
        user = await self.get_user_by_telegram_id(telegram_user_id)
        if user is None:
            return None
        return next((item for item in user.subscriptions if item.id == subscription_id), None)

    async def get_active_subscription_for_product(self, user_id: str, product_id: str) -> Subscription | None:
        query = (
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.product_id == product_id,
                Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
            )
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_active_product_ids_for_user(self, user_id: str) -> set[str]:
        query = select(Subscription.product_id).where(
            Subscription.user_id == user_id,
            Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
        )
        result = await self.session.execute(query)
        return set(result.scalars().all())

    def add(self, entity: object) -> None:
        self.session.add(entity)

    async def flush(self) -> None:
        await self.session.flush()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def commit(self) -> None:
        await self.session.commit()

    async def refresh(self, entity: object) -> None:
        await self.session.refresh(entity)


class FilePublicRepository(PublicRepository):
    REQUIRED_CHECKOUT_DOCUMENT_TYPES = (
        LegalDocumentType.DISCLAIMER,
        LegalDocumentType.OFFER,
        LegalDocumentType.PRIVACY_POLICY,
        LegalDocumentType.PAYMENT_CONSENT,
    )

    def __init__(self, store: FileDataStore | None = None) -> None:
        self.store = store or FileDataStore()
        self.graph = FileDatasetGraph.load(self.store)

    async def list_public_strategies(self) -> list[Strategy]:
        items = [
            item
            for item in self.graph.strategies.values()
            if item.is_public and item.status == StrategyStatus.PUBLISHED
        ]
        for strategy in items:
            strategy.subscription_products = [product for product in strategy.subscription_products if product.is_active]
        items.sort(key=lambda item: (item.created_at, item.title.lower()), reverse=True)
        return items

    async def get_public_strategy_by_slug(self, slug: str) -> Strategy | None:
        for strategy in self.graph.strategies.values():
            if strategy.slug == slug and strategy.is_public and strategy.status == StrategyStatus.PUBLISHED:
                strategy.subscription_products = [product for product in strategy.subscription_products if product.is_active]
                return strategy
        return None

    async def get_public_product(self, product_id: str) -> SubscriptionProduct | None:
        product = self.graph.products.get(product_id)
        if product is None or not product.is_active:
            return None
        if product.strategy is not None and (not product.strategy.is_public or product.strategy.status != StrategyStatus.PUBLISHED):
            return None
        return product

    async def get_public_product_by_slug(self, slug: str) -> SubscriptionProduct | None:
        product = next((item for item in self.graph.products.values() if item.slug == slug), None)
        if product is None:
            return None
        return await self.get_public_product(product.id)

    async def get_public_product_by_ref(self, product_ref: str) -> SubscriptionProduct | None:
        normalized = (product_ref or "").strip()
        if not normalized:
            return None
        product = await self.get_public_product_by_slug(normalized)
        if product is not None:
            return product
        return await self.get_public_product(normalized)

    async def list_active_checkout_documents(self) -> list[LegalDocument]:
        by_type: dict[LegalDocumentType, LegalDocument] = {}
        for document in sorted(
            self.graph.legal_documents.values(),
            key=lambda item: (item.document_type.value, item.version),
            reverse=True,
        ):
            if document.is_active and document.document_type in self.REQUIRED_CHECKOUT_DOCUMENT_TYPES:
                by_type.setdefault(document.document_type, document)
        return [by_type[item] for item in self.REQUIRED_CHECKOUT_DOCUMENT_TYPES if item in by_type]

    async def find_active_promo_by_code(self, code: str) -> PromoCode | None:
        normalized = code.strip().upper()
        if not normalized:
            return None
        promo = next((item for item in self.graph.promo_codes.values() if item.code == normalized), None)
        if promo is None or not promo.is_active:
            return None
        return promo

    async def get_lead_source_by_name(self, name: str) -> LeadSource | None:
        normalized = name.strip().lower()
        if not normalized:
            return None
        return next((item for item in self.graph.lead_sources.values() if item.name.lower() == normalized), None)

    async def find_user_by_email(self, email: str) -> User | None:
        return next((item for item in self.graph.users.values() if item.email == email), None)

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> User | None:
        return next((item for item in self.graph.users.values() if item.telegram_user_id == telegram_user_id), None)

    async def get_user_payment(self, *, telegram_user_id: int, payment_id: str) -> Payment | None:
        user = await self.get_user_by_telegram_id(telegram_user_id)
        if user is None:
            return None
        return next((item for item in user.payments if item.id == payment_id), None)

    async def get_user_subscription(self, *, telegram_user_id: int, subscription_id: str) -> Subscription | None:
        user = await self.get_user_by_telegram_id(telegram_user_id)
        if user is None:
            return None
        return next((item for item in user.subscriptions if item.id == subscription_id), None)

    async def get_active_subscription_for_product(self, user_id: str, product_id: str) -> Subscription | None:
        return next(
            (
                item
                for item in self.graph.subscriptions.values()
                if item.user_id == user_id and item.product_id == product_id and item.status in ACTIVE_SUBSCRIPTION_STATUSES
            ),
            None,
        )

    async def list_active_product_ids_for_user(self, user_id: str) -> set[str]:
        return {
            item.product_id
            for item in self.graph.subscriptions.values()
            if item.user_id == user_id and item.status in ACTIVE_SUBSCRIPTION_STATUSES
        }

    def add(self, entity: object) -> None:
        self.graph.add(entity)

    async def flush(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def commit(self) -> None:
        self.graph.save(self.store)

    async def refresh(self, entity: object) -> None:
        return None
