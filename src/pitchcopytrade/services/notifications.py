from __future__ import annotations

import logging

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.audit import AuditEvent
from pitchcopytrade.db.models.catalog import BundleMember, SubscriptionProduct
from pitchcopytrade.db.models.commerce import Subscription
from pitchcopytrade.db.models.content import Recommendation
from pitchcopytrade.db.models.enums import SubscriptionStatus


logger = logging.getLogger(__name__)
ACTIVE_SUBSCRIPTION_STATUSES = (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL)


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
) -> list[int]:
    recipients = await list_recommendation_recipient_telegram_ids(session, recommendation)
    text = build_recommendation_notification_text(recommendation)
    delivered: list[int] = []
    for chat_id in recipients:
        try:
            await notifier.send_message(chat_id, text)
            delivered.append(chat_id)
        except Exception:
            logger.exception("Failed to deliver recommendation notification to chat_id=%s", chat_id)

    session.add(
        AuditEvent(
            actor_user_id=None,
            entity_type="recommendation",
            entity_id=recommendation.id,
            action="notification.delivery",
            payload={"recipient_count": len(delivered)},
        )
    )
    await session.commit()
    return delivered
