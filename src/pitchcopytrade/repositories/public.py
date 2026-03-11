from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import LegalDocument, Payment, Subscription, UserConsent
from pitchcopytrade.db.models.enums import LegalDocumentType, StrategyStatus
from pitchcopytrade.repositories.contracts import PublicRepository
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore


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
        return await self.get_public_product(product.id)

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

    async def find_user_by_email(self, email: str) -> User | None:
        query = select(User).options(selectinload(User.consents)).where(User.email == email)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> User | None:
        query = select(User).options(selectinload(User.consents)).where(User.telegram_user_id == telegram_user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    def add(self, entity: object) -> None:
        self.session.add(entity)

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

    async def find_user_by_email(self, email: str) -> User | None:
        return next((item for item in self.graph.users.values() if item.email == email), None)

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> User | None:
        return next((item for item in self.graph.users.values() if item.telegram_user_id == telegram_user_id), None)

    def add(self, entity: object) -> None:
        self.graph.add(entity)

    async def commit(self) -> None:
        self.graph.save(self.store)

    async def refresh(self, entity: object) -> None:
        return None
