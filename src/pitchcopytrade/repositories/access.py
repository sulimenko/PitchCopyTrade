from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.audit import AuditEvent
from pitchcopytrade.db.models.catalog import BundleMember, Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import Payment, PromoCode, Subscription
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.enums import MessageDeliver, MessageStatus, SubscriptionStatus
from pitchcopytrade.repositories.contracts import AccessRepository
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore


ACTIVE_SUBSCRIPTION_STATUSES = (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL)
VISIBLE_MESSAGE_STATUSES = (MessageStatus.PUBLISHED,)


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

    async def list_user_visible_messages(self, *, user_id: str, limit: int = 20) -> list[Message]:
        query: Select[tuple[Message]] = (
            select(Message)
            .options(
                selectinload(Message.strategy).selectinload(Strategy.author),
                selectinload(Message.author).selectinload(AuthorProfile.user),
                selectinload(Message.bundle),
            )
            .where(
                Message.published.is_not(None),
                Message.status.in_(VISIBLE_MESSAGE_STATUSES),
            )
            .order_by(Message.published.desc(), Message.created.desc())
        )
        result = await self.session.execute(query)
        strategy_ids, author_ids, bundle_strategy_ids = await self._build_user_access_scope(user_id)
        items = [
            item
            for item in result.scalars().all()
            if _message_matches_audience(
                item,
                strategy_ids=strategy_ids,
                author_ids=author_ids,
                bundle_strategy_ids=bundle_strategy_ids,
            )
        ]
        items.sort(key=lambda item: (item.published or item.created, item.created), reverse=True)
        return items[:limit]

    async def get_user_visible_message(self, *, user_id: str, message_id: str) -> Message | None:
        query = (
            select(Message)
            .options(
                selectinload(Message.strategy).selectinload(Strategy.author),
                selectinload(Message.author).selectinload(AuthorProfile.user),
                selectinload(Message.bundle),
            )
            .where(
                Message.id == message_id,
                Message.published.is_not(None),
                Message.status.in_(VISIBLE_MESSAGE_STATUSES),
            )
        )
        result = await self.session.execute(query)
        message = result.scalar_one_or_none()
        if message is None:
            return None
        strategy_ids, author_ids, bundle_strategy_ids = await self._build_user_access_scope(user_id)
        if not _message_matches_audience(
            message,
            strategy_ids=strategy_ids,
            author_ids=author_ids,
            bundle_strategy_ids=bundle_strategy_ids,
        ):
            return None
        return message

    async def list_user_visible_recommendations(self, *, user_id: str, limit: int = 20) -> list[Message]:
        return await self.list_user_visible_messages(user_id=user_id, limit=limit)

    async def get_user_visible_recommendation(self, *, user_id: str, recommendation_id: str) -> Message | None:
        return await self.get_user_visible_message(user_id=user_id, message_id=recommendation_id)

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> User | None:
        query = (
            select(User)
            .options(
                selectinload(User.roles),
                selectinload(User.payments).selectinload(Payment.product),
                selectinload(User.subscriptions).selectinload(Subscription.product),
                selectinload(User.subscriptions).selectinload(Subscription.payment),
                selectinload(User.subscriptions).selectinload(Subscription.applied_promo_code),
            )
            .where(User.telegram_user_id == telegram_user_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def commit(self) -> None:
        await self.session.commit()

    async def list_user_reminder_events(self, *, user_id: str, limit: int = 20) -> list[AuditEvent]:
        query = (
            select(AuditEvent)
            .where(AuditEvent.action == "notification.reminder")
            .order_by(AuditEvent.created_at.desc())
        )
        result = await self.session.execute(query)
        items = [
            event
            for event in result.scalars().all()
            if str((event.payload or {}).get("user_id")) == user_id
        ]
        return items[:limit]

    async def get_notification_preferences(self, *, user_id: str) -> dict[str, bool]:
        query = (
            select(AuditEvent)
            .where(AuditEvent.action == "subscriber.notification_preferences")
            .order_by(AuditEvent.created_at.desc())
        )
        result = await self.session.execute(query)
        for event in result.scalars().all():
            payload = event.payload or {}
            if str(payload.get("user_id")) == user_id:
                return {
                    "payment_reminders": bool(payload.get("payment_reminders", True)),
                    "subscription_reminders": bool(payload.get("subscription_reminders", True)),
                }
        return {
            "payment_reminders": True,
            "subscription_reminders": True,
        }

    async def save_notification_preferences(self, *, user_id: str, preferences: dict[str, bool]) -> dict[str, bool]:
        normalized = {
            "payment_reminders": bool(preferences.get("payment_reminders", True)),
            "subscription_reminders": bool(preferences.get("subscription_reminders", True)),
        }
        self.session.add(
            AuditEvent(
                actor_user_id=user_id,
                entity_type="user",
                entity_id=user_id,
                action="subscriber.notification_preferences",
                payload={"user_id": user_id, **normalized},
            )
        )
        await self.session.commit()
        return normalized

    async def _build_user_access_scope(self, user_id: str) -> tuple[set[str], set[str], set[str]]:
        result = await self.session.execute(
            select(
                SubscriptionProduct.strategy_id,
                SubscriptionProduct.author_id,
                SubscriptionProduct.bundle_id,
            )
            .join(Subscription, Subscription.product_id == SubscriptionProduct.id)
            .where(
                Subscription.user_id == user_id,
                Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
            )
        )
        strategy_ids: set[str] = set()
        author_ids: set[str] = set()
        bundle_ids: set[str] = set()
        for strategy_id, author_id, bundle_id in result.all():
            if strategy_id is not None:
                strategy_ids.add(strategy_id)
            if author_id is not None:
                author_ids.add(author_id)
            if bundle_id is not None:
                bundle_ids.add(bundle_id)

        bundle_strategy_ids: set[str] = set()
        if bundle_ids:
            bundle_result = await self.session.execute(
                select(BundleMember.strategy_id).where(BundleMember.bundle_id.in_(bundle_ids))
            )
            bundle_strategy_ids.update(item for item in bundle_result.scalars().all() if item is not None)
        return strategy_ids, author_ids, bundle_strategy_ids


class FileAccessRepository(AccessRepository):
    def __init__(self, store: FileDataStore | None = None) -> None:
        self.store = store or FileDataStore()
        self.graph = FileDatasetGraph.load(self.store)

    async def user_has_active_access(self, user_id: str) -> bool:
        return any(
            item.user_id == user_id and item.status in ACTIVE_SUBSCRIPTION_STATUSES
            for item in self.graph.subscriptions.values()
        )

    async def list_user_visible_messages(self, *, user_id: str, limit: int = 20) -> list[Message]:
        allowed_strategy_ids = self._allowed_strategy_ids(user_id)
        allowed_author_ids = self._allowed_author_ids(user_id)
        allowed_bundle_strategy_ids = self._allowed_bundle_strategy_ids(user_id)
        items = [
            item
            for item in self.graph.messages.values()
            if item.published is not None
            and item.status in {status.value for status in VISIBLE_MESSAGE_STATUSES}
            and _message_matches_audience(
                item,
                strategy_ids=allowed_strategy_ids,
                author_ids=allowed_author_ids,
                bundle_strategy_ids=allowed_bundle_strategy_ids,
            )
        ]
        items.sort(key=lambda item: (item.published or item.created, item.created), reverse=True)
        return items[:limit]

    async def get_user_visible_message(self, *, user_id: str, message_id: str) -> Message | None:
        message = self.graph.messages.get(message_id)
        if message is None:
            return None
        allowed_strategy_ids = self._allowed_strategy_ids(user_id)
        allowed_author_ids = self._allowed_author_ids(user_id)
        allowed_bundle_strategy_ids = self._allowed_bundle_strategy_ids(user_id)
        if message.published is None or message.status not in {status.value for status in VISIBLE_MESSAGE_STATUSES}:
            return None
        if not _message_matches_audience(
            message,
            strategy_ids=allowed_strategy_ids,
            author_ids=allowed_author_ids,
            bundle_strategy_ids=allowed_bundle_strategy_ids,
        ):
            return None
        return message

    async def list_user_visible_recommendations(self, *, user_id: str, limit: int = 20) -> list[Message]:
        return await self.list_user_visible_messages(user_id=user_id, limit=limit)

    async def get_user_visible_recommendation(self, *, user_id: str, recommendation_id: str) -> Message | None:
        return await self.get_user_visible_message(user_id=user_id, message_id=recommendation_id)

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> User | None:
        return next((item for item in self.graph.users.values() if item.telegram_user_id == telegram_user_id), None)

    async def commit(self) -> None:
        self.graph.save(self.store)

    async def list_user_reminder_events(self, *, user_id: str, limit: int = 20) -> list[AuditEvent]:
        items = [
            event
            for event in self.graph.audit_events.values()
            if event.action == "notification.reminder" and str((event.payload or {}).get("user_id")) == user_id
        ]
        items.sort(key=lambda event: event.created_at, reverse=True)
        return items[:limit]

    async def get_notification_preferences(self, *, user_id: str) -> dict[str, bool]:
        events = [
            event
            for event in self.graph.audit_events.values()
            if event.action == "subscriber.notification_preferences" and str((event.payload or {}).get("user_id")) == user_id
        ]
        events.sort(key=lambda event: event.created_at, reverse=True)
        if events:
            payload = events[0].payload or {}
            return {
                "payment_reminders": bool(payload.get("payment_reminders", True)),
                "subscription_reminders": bool(payload.get("subscription_reminders", True)),
            }
        return {
            "payment_reminders": True,
            "subscription_reminders": True,
        }

    async def save_notification_preferences(self, *, user_id: str, preferences: dict[str, bool]) -> dict[str, bool]:
        normalized = {
            "payment_reminders": bool(preferences.get("payment_reminders", True)),
            "subscription_reminders": bool(preferences.get("subscription_reminders", True)),
        }
        self.graph.add(
            AuditEvent(
                actor_user_id=user_id,
                entity_type="user",
                entity_id=user_id,
                action="subscriber.notification_preferences",
                payload={"user_id": user_id, **normalized},
            )
        )
        self.graph.save(self.store)
        return normalized

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

    def _allowed_bundle_strategy_ids(self, user_id: str) -> set[str]:
        bundle_ids = {
            product.bundle_id
            for product in self._active_products_for_user(user_id)
            if product.bundle_id is not None
        }
        return {
            member.strategy_id
            for member in self.graph.bundle_members
            if member.bundle_id in bundle_ids
        }


def _message_matches_audience(
    message: Message,
    *,
    strategy_ids: set[str],
    author_ids: set[str],
    bundle_strategy_ids: set[str],
) -> bool:
    deliver = {str(item).strip() for item in (message.deliver or []) if str(item).strip()}
    if not deliver:
        return False
    if MessageDeliver.STRATEGY.value in deliver and message.strategy_id in strategy_ids:
        return True
    if MessageDeliver.AUTHOR.value in deliver and message.author_id in author_ids:
        return True
    if MessageDeliver.BUNDLE.value in deliver and message.strategy_id in bundle_strategy_ids:
        return True
    return False
