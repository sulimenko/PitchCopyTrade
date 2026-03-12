from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.audit import AuditEvent
from pitchcopytrade.db.models.catalog import BundleMember, SubscriptionProduct
from pitchcopytrade.db.models.commerce import Subscription
from pitchcopytrade.db.models.content import Recommendation
from pitchcopytrade.db.models.enums import SubscriptionStatus
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore


logger = logging.getLogger(__name__)
ACTIVE_SUBSCRIPTION_STATUSES = (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL)
DEFAULT_NOTIFICATION_ATTEMPTS = 3


async def list_recommendation_recipient_telegram_ids(
    session: AsyncSession,
    recommendation: Recommendation,
) -> list[int]:
    query = (
        select(User.telegram_user_id)
        .join(Subscription, Subscription.user_id == User.id)
        .join(SubscriptionProduct, Subscription.product_id == SubscriptionProduct.id)
        .where(
            User.telegram_user_id.is_not(None),
            Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
            or_(
                SubscriptionProduct.strategy_id == recommendation.strategy_id,
                SubscriptionProduct.author_id == recommendation.author_id,
                SubscriptionProduct.bundle_id.in_(
                    select(BundleMember.bundle_id).where(BundleMember.strategy_id == recommendation.strategy_id)
                ),
            ),
        )
        .distinct()
    )
    result = await session.execute(query)
    return [int(item) for item in result.scalars().all() if item is not None]


def build_recommendation_notification_text(recommendation: Recommendation) -> str:
    title = recommendation.title or recommendation.strategy.title
    lines = [
        "Новая публикация по вашей подписке",
        f"{title}",
        f"Стратегия: {recommendation.strategy.title}",
        f"Тип: {recommendation.kind.value}",
    ]
    if recommendation.summary:
        lines.append(recommendation.summary)
    if recommendation.legs:
        first_leg = recommendation.legs[0]
        instrument = first_leg.instrument.ticker if first_leg.instrument else "инструмент"
        lines.append(
            f"Leg: {instrument} {first_leg.side.value if first_leg.side else 'n/a'} "
            f"{first_leg.entry_from or 'n/a'}"
        )
    if recommendation.attachments:
        lines.append(f"Вложений: {len(recommendation.attachments)}")
    return "\n".join(lines)


async def deliver_recommendation_notifications(
    session: AsyncSession,
    recommendation: Recommendation,
    notifier,
    *,
    trigger: str = "publish",
    attempts: int = DEFAULT_NOTIFICATION_ATTEMPTS,
) -> list[int]:
    recipients = await list_recommendation_recipient_telegram_ids(session, recommendation)
    text = build_recommendation_notification_text(recommendation)
    delivered: list[int] = []
    for chat_id in recipients:
        if await _send_with_retry(notifier.send_message, chat_id, text, attempts=attempts):
            delivered.append(chat_id)

    session.add(
        AuditEvent(
            actor_user_id=None,
            entity_type="recommendation",
            entity_id=recommendation.id,
            action="notification.delivery",
            payload={
                "recipient_count": len(delivered),
                "attempted_count": len(recipients),
                "failed_count": len(recipients) - len(delivered),
                "trigger": trigger,
                "attempts": attempts,
            },
        )
    )
    await session.commit()
    return delivered


async def deliver_recommendation_notifications_file(
    graph: FileDatasetGraph,
    store: FileDataStore,
    recommendation: Recommendation,
    notifier,
    *,
    trigger: str = "publish",
    attempts: int = DEFAULT_NOTIFICATION_ATTEMPTS,
) -> list[int]:
    recipients = {
        subscription.user.telegram_user_id
        for subscription in graph.subscriptions.values()
        if subscription.status in ACTIVE_SUBSCRIPTION_STATUSES
        and subscription.user.telegram_user_id is not None
        and (
            subscription.product.strategy_id == recommendation.strategy_id
            or subscription.product.author_id == recommendation.author_id
            or (
                subscription.product.bundle_id is not None
                and any(
                    member.bundle_id == subscription.product.bundle_id and member.strategy_id == recommendation.strategy_id
                    for member in graph.bundle_members
                )
            )
        )
    }
    text = build_recommendation_notification_text(recommendation)
    delivered: list[int] = []
    for chat_id in sorted(int(item) for item in recipients if item is not None):
        if await _send_with_retry(notifier.send_message, chat_id, text, attempts=attempts):
            delivered.append(chat_id)

    graph.add(
        AuditEvent(
            actor_user_id=None,
            entity_type="recommendation",
            entity_id=recommendation.id,
            action="notification.delivery",
            payload={
                "recipient_count": len(delivered),
                "attempted_count": len(recipients),
                "failed_count": len(recipients) - len(delivered),
                "trigger": trigger,
                "attempts": attempts,
            },
        )
    )
    graph.save(store)
    return delivered


async def _send_with_retry(
    send_message: Callable[[int, str], Awaitable[object]],
    chat_id: int,
    text: str,
    *,
    attempts: int,
) -> bool:
    for attempt in range(1, attempts + 1):
        try:
            await send_message(chat_id, text)
            if attempt > 1:
                logger.info("Notification delivery recovered on retry %s for chat_id=%s", attempt, chat_id)
            return True
        except Exception:
            logger.exception(
                "Failed to deliver recommendation notification to chat_id=%s attempt=%s/%s",
                chat_id,
                attempt,
                attempts,
            )
    return False
