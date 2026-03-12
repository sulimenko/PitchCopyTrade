from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.audit import AuditEvent
from pitchcopytrade.db.models.catalog import BundleMember, SubscriptionProduct
from pitchcopytrade.db.models.commerce import Payment, Subscription
from pitchcopytrade.db.models.content import Recommendation
from pitchcopytrade.db.models.enums import PaymentStatus, SubscriptionStatus
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore


logger = logging.getLogger(__name__)
ACTIVE_SUBSCRIPTION_STATUSES = (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL)
DEFAULT_NOTIFICATION_ATTEMPTS = 3
SUBSCRIPTION_REMINDER_WINDOW = timedelta(days=3)
PAYMENT_REMINDER_WINDOW = timedelta(hours=6)


@dataclass(slots=True)
class ReminderStats:
    sent: int = 0
    skipped: int = 0


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


async def deliver_subscriber_reminders(
    session: AsyncSession | None,
    notifier,
    *,
    now: datetime | None = None,
    store: FileDataStore | None = None,
    attempts: int = DEFAULT_NOTIFICATION_ATTEMPTS,
) -> ReminderStats:
    timestamp = now or datetime.now(timezone.utc)
    if session is None:
        runtime_store = store or FileDataStore()
        graph = FileDatasetGraph.load(runtime_store)
        return await _deliver_subscriber_reminders_file(graph, runtime_store, notifier, now=timestamp, attempts=attempts)
    return await _deliver_subscriber_reminders_db(session, notifier, now=timestamp, attempts=attempts)


async def _deliver_subscriber_reminders_db(
    session: AsyncSession,
    notifier,
    *,
    now: datetime,
    attempts: int,
) -> ReminderStats:
    stats = ReminderStats()
    sent_keys = await _load_existing_reminder_keys_db(session)
    subscriptions = await _list_db_subscription_reminders(session, now=now)
    payments = await _list_db_payment_reminders(session, now=now)

    for subscription in subscriptions:
        key = _subscription_reminder_key(subscription)
        if key in sent_keys:
            stats.skipped += 1
            continue
        text = _build_subscription_reminder_text(subscription)
        if await _send_with_retry(notifier.send_message, int(subscription.user.telegram_user_id), text, attempts=attempts):
            session.add(_build_reminder_event("subscription", subscription.id, key, "subscription_expiring"))
            sent_keys.add(key)
            stats.sent += 1

    for payment in payments:
        key = _payment_reminder_key(payment)
        if key in sent_keys:
            stats.skipped += 1
            continue
        text = _build_payment_reminder_text(payment)
        if await _send_with_retry(notifier.send_message, int(payment.user.telegram_user_id), text, attempts=attempts):
            session.add(_build_reminder_event("payment", payment.id, key, "payment_pending"))
            sent_keys.add(key)
            stats.sent += 1

    if stats.sent:
        await session.commit()
    return stats


async def _deliver_subscriber_reminders_file(
    graph: FileDatasetGraph,
    store: FileDataStore,
    notifier,
    *,
    now: datetime,
    attempts: int,
) -> ReminderStats:
    stats = ReminderStats()
    sent_keys = _load_existing_reminder_keys_file(graph)

    for subscription in _list_file_subscription_reminders(graph, now=now):
        key = _subscription_reminder_key(subscription)
        if key in sent_keys:
            stats.skipped += 1
            continue
        text = _build_subscription_reminder_text(subscription)
        if await _send_with_retry(notifier.send_message, int(subscription.user.telegram_user_id), text, attempts=attempts):
            graph.add(_build_reminder_event("subscription", subscription.id, key, "subscription_expiring"))
            sent_keys.add(key)
            stats.sent += 1

    for payment in _list_file_payment_reminders(graph, now=now):
        key = _payment_reminder_key(payment)
        if key in sent_keys:
            stats.skipped += 1
            continue
        text = _build_payment_reminder_text(payment)
        if await _send_with_retry(notifier.send_message, int(payment.user.telegram_user_id), text, attempts=attempts):
            graph.add(_build_reminder_event("payment", payment.id, key, "payment_pending"))
            sent_keys.add(key)
            stats.sent += 1

    if stats.sent:
        graph.save(store)
    return stats


async def _load_existing_reminder_keys_db(session: AsyncSession) -> set[str]:
    query = select(AuditEvent).where(AuditEvent.action == "notification.reminder")
    result = await session.execute(query)
    return {
        str((item.payload or {}).get("reminder_key"))
        for item in result.scalars().all()
        if (item.payload or {}).get("reminder_key") is not None
    }


def _load_existing_reminder_keys_file(graph: FileDatasetGraph) -> set[str]:
    return {
        str((item.payload or {}).get("reminder_key"))
        for item in graph.audit_events.values()
        if item.action == "notification.reminder" and (item.payload or {}).get("reminder_key") is not None
    }


async def _list_db_subscription_reminders(session: AsyncSession, *, now: datetime) -> list[Subscription]:
    query = (
        select(Subscription)
        .options(selectinload(Subscription.user), selectinload(Subscription.product))
        .join(User, Subscription.user_id == User.id)
        .where(
            Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
            Subscription.end_at <= now + SUBSCRIPTION_REMINDER_WINDOW,
            User.telegram_user_id.is_not(None),
        )
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def _list_db_payment_reminders(session: AsyncSession, *, now: datetime) -> list[Payment]:
    query = (
        select(Payment)
        .options(selectinload(Payment.user), selectinload(Payment.product))
        .join(User, Payment.user_id == User.id)
        .where(
            Payment.status == PaymentStatus.PENDING,
            Payment.expires_at.is_not(None),
            Payment.expires_at <= now + PAYMENT_REMINDER_WINDOW,
            User.telegram_user_id.is_not(None),
        )
    )
    result = await session.execute(query)
    return list(result.scalars().all())


def _list_file_subscription_reminders(graph: FileDatasetGraph, *, now: datetime) -> list[Subscription]:
    return [
        item
        for item in graph.subscriptions.values()
        if item.status in ACTIVE_SUBSCRIPTION_STATUSES
        and item.end_at is not None
        and item.end_at <= now + SUBSCRIPTION_REMINDER_WINDOW
        and item.user.telegram_user_id is not None
    ]


def _list_file_payment_reminders(graph: FileDatasetGraph, *, now: datetime) -> list[Payment]:
    return [
        item
        for item in graph.payments.values()
        if item.status is PaymentStatus.PENDING
        and item.expires_at is not None
        and item.expires_at <= now + PAYMENT_REMINDER_WINDOW
        and item.user.telegram_user_id is not None
    ]


def _subscription_reminder_key(subscription: Subscription) -> str:
    end_marker = subscription.end_at.isoformat() if subscription.end_at is not None else "na"
    return f"subscription:{subscription.id}:{end_marker}"


def _payment_reminder_key(payment: Payment) -> str:
    expire_marker = payment.expires_at.isoformat() if payment.expires_at is not None else "na"
    return f"payment:{payment.id}:{expire_marker}"


def _build_subscription_reminder_text(subscription: Subscription) -> str:
    title = subscription.product.title if subscription.product is not None else "Подписка"
    return (
        f"Скоро закончится подписка: {title}\n"
        f"Действует до: {subscription.end_at}\n"
        "Откройте Mini App и продлите подписку заранее, чтобы не потерять доступ."
    )


def _build_payment_reminder_text(payment: Payment) -> str:
    title = payment.product.title if payment.product is not None else "Оплата"
    return (
        f"Оплата ожидает завершения: {title}\n"
        f"Срок заявки: {payment.expires_at}\n"
        "Откройте Mini App, обновите статус или завершите оплату до истечения срока."
    )


def _build_reminder_event(entity_type: str, entity_id: str, reminder_key: str, reminder_kind: str) -> AuditEvent:
    return AuditEvent(
        actor_user_id=None,
        entity_type=entity_type,
        entity_id=entity_id,
        action="notification.reminder",
        payload={
            "reminder_key": reminder_key,
            "kind": reminder_kind,
        },
    )
