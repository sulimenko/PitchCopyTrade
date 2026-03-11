from __future__ import annotations

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import BundleMember, Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import Subscription
from pitchcopytrade.db.models.content import Recommendation, RecommendationLeg
from pitchcopytrade.db.models.enums import RecommendationStatus, SubscriptionStatus
from pitchcopytrade.repositories.contracts import AccessRepository
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore


ACTIVE_SUBSCRIPTION_STATUSES = (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL)
VISIBLE_RECOMMENDATION_STATUSES = (
    RecommendationStatus.PUBLISHED,
    RecommendationStatus.CLOSED,
    RecommendationStatus.CANCELLED,
)


class SqlAlchemyAccessRepository(AccessRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def user_has_active_access(self, user_id: str) -> bool:
        query = (
            select(Subscription.id)
            .where(
                Subscription.user_id == user_id,
                Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
            )
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def list_user_visible_recommendations(
        self,
        *,
        user_id: str,
        limit: int = 20,
    ) -> list[Recommendation]:
        query: Select[tuple[Recommendation]] = (
            select(Recommendation)
            .options(
                selectinload(Recommendation.strategy).selectinload(Strategy.author),
                selectinload(Recommendation.author).selectinload(AuthorProfile.user),
                selectinload(Recommendation.legs).selectinload(RecommendationLeg.instrument),
                selectinload(Recommendation.attachments),
            )
            .where(
                self._build_user_access_filter(user_id),
                Recommendation.published_at.is_not(None),
                Recommendation.status.in_(VISIBLE_RECOMMENDATION_STATUSES),
            )
            .order_by(Recommendation.published_at.desc(), Recommendation.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_user_visible_recommendation(
        self,
        *,
        user_id: str,
        recommendation_id: str,
    ) -> Recommendation | None:
        query = (
            select(Recommendation)
            .options(
                selectinload(Recommendation.strategy).selectinload(Strategy.author),
                selectinload(Recommendation.author).selectinload(AuthorProfile.user),
                selectinload(Recommendation.legs).selectinload(RecommendationLeg.instrument),
                selectinload(Recommendation.attachments),
            )
            .where(
                Recommendation.id == recommendation_id,
                self._build_user_access_filter(user_id),
                Recommendation.published_at.is_not(None),
                Recommendation.status.in_(VISIBLE_RECOMMENDATION_STATUSES),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> User | None:
        query = select(User).options(selectinload(User.roles)).where(User.telegram_user_id == telegram_user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    def _build_user_access_filter(self, user_id: str):
        strategy_ids = (
            select(SubscriptionProduct.strategy_id)
            .join(Subscription, Subscription.product_id == SubscriptionProduct.id)
            .where(
                Subscription.user_id == user_id,
                Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
                SubscriptionProduct.strategy_id.is_not(None),
            )
        )
        author_ids = (
            select(SubscriptionProduct.author_id)
            .join(Subscription, Subscription.product_id == SubscriptionProduct.id)
            .where(
                Subscription.user_id == user_id,
                Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
                SubscriptionProduct.author_id.is_not(None),
            )
        )
        bundle_strategy_ids = (
            select(BundleMember.strategy_id)
            .join(SubscriptionProduct, SubscriptionProduct.bundle_id == BundleMember.bundle_id)
            .join(Subscription, Subscription.product_id == SubscriptionProduct.id)
            .where(
                Subscription.user_id == user_id,
                Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
                SubscriptionProduct.bundle_id.is_not(None),
            )
        )
        return or_(
            Recommendation.strategy_id.in_(strategy_ids),
            Recommendation.author_id.in_(author_ids),
            Recommendation.strategy_id.in_(bundle_strategy_ids),
        )


class FileAccessRepository(AccessRepository):
    def __init__(self, store: FileDataStore | None = None) -> None:
        self.store = store or FileDataStore()
        self.graph = FileDatasetGraph.load(self.store)

    async def user_has_active_access(self, user_id: str) -> bool:
        return any(
            item.user_id == user_id and item.status in ACTIVE_SUBSCRIPTION_STATUSES
            for item in self.graph.subscriptions.values()
        )

    async def list_user_visible_recommendations(
        self,
        *,
        user_id: str,
        limit: int = 20,
    ) -> list[Recommendation]:
        allowed_strategy_ids = self._allowed_strategy_ids(user_id)
        allowed_author_ids = self._allowed_author_ids(user_id)
        items = [
            item
            for item in self.graph.recommendations.values()
            if item.published_at is not None
            and item.status in VISIBLE_RECOMMENDATION_STATUSES
            and (item.strategy_id in allowed_strategy_ids or item.author_id in allowed_author_ids)
        ]
        items.sort(key=lambda item: (item.published_at or item.created_at, item.created_at), reverse=True)
        return items[:limit]

    async def get_user_visible_recommendation(
        self,
        *,
        user_id: str,
        recommendation_id: str,
    ) -> Recommendation | None:
        recommendation = self.graph.recommendations.get(recommendation_id)
        if recommendation is None:
            return None
        allowed_strategy_ids = self._allowed_strategy_ids(user_id)
        allowed_author_ids = self._allowed_author_ids(user_id)
        if recommendation.published_at is None or recommendation.status not in VISIBLE_RECOMMENDATION_STATUSES:
            return None
        if recommendation.strategy_id not in allowed_strategy_ids and recommendation.author_id not in allowed_author_ids:
            return None
        return recommendation

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> User | None:
        return next((item for item in self.graph.users.values() if item.telegram_user_id == telegram_user_id), None)

    def _active_products_for_user(self, user_id: str) -> list[SubscriptionProduct]:
        products: list[SubscriptionProduct] = []
        for subscription in self.graph.subscriptions.values():
            if subscription.user_id == user_id and subscription.status in ACTIVE_SUBSCRIPTION_STATUSES:
                product = self.graph.products.get(subscription.product_id)
                if product is not None:
                    products.append(product)
        return products

    def _allowed_strategy_ids(self, user_id: str) -> set[str]:
        strategy_ids: set[str] = set()
        for product in self._active_products_for_user(user_id):
            if product.strategy_id:
                strategy_ids.add(product.strategy_id)
            if product.bundle_id:
                for member in self.graph.bundle_members:
                    if member.bundle_id == product.bundle_id:
                        strategy_ids.add(member.strategy_id)
        return strategy_ids

    def _allowed_author_ids(self, user_id: str) -> set[str]:
        return {
            product.author_id
            for product in self._active_products_for_user(user_id)
            if product.author_id is not None
        }
