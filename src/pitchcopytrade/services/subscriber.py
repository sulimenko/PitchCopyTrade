from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.commerce import Payment, Subscription
from pitchcopytrade.db.models.enums import PaymentStatus, SubscriptionStatus
from pitchcopytrade.repositories.contracts import AccessRepository
from pitchcopytrade.services.acl import get_user_by_telegram_id, list_user_visible_recommendations, user_has_active_access


ACTIVE_SUBSCRIPTION_STATUSES = {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL}


@dataclass(slots=True)
class SubscriberStatusSnapshot:
    user: User
    has_access: bool
    active_subscriptions: list[Subscription]
    pending_payments: list[Payment]
    visible_recommendation_titles: list[str]


async def get_subscriber_status_snapshot(
    repository: AccessRepository,
    *,
    telegram_user_id: int,
    recommendation_limit: int = 5,
) -> SubscriberStatusSnapshot | None:
    user = await get_user_by_telegram_id(repository, telegram_user_id)
    if user is None:
        return None

    has_access = await user_has_active_access(repository, user_id=user.id)
    recommendations = await list_user_visible_recommendations(
        repository,
        user_id=user.id,
        limit=recommendation_limit,
    )
    active_subscriptions = sorted(
        [
            item
            for item in (user.subscriptions or [])
            if item.status in ACTIVE_SUBSCRIPTION_STATUSES
        ],
        key=lambda item: item.end_at or datetime.min,
        reverse=True,
    )
    pending_payments = sorted(
        [
            item
            for item in (user.payments or [])
            if item.status is PaymentStatus.PENDING
        ],
        key=lambda item: item.created_at or datetime.min,
        reverse=True,
    )
    visible_titles = [item.title or item.strategy.title for item in recommendations]
    return SubscriberStatusSnapshot(
        user=user,
        has_access=has_access,
        active_subscriptions=active_subscriptions,
        pending_payments=pending_payments,
        visible_recommendation_titles=visible_titles,
    )
