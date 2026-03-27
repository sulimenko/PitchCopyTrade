from __future__ import annotations

import logging
from html import escape
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.audit import AuditEvent
from pitchcopytrade.db.models.catalog import BundleMember, SubscriptionProduct
from pitchcopytrade.db.models.commerce import Payment, Subscription
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.enums import MessageDeliver, MessageStatus, PaymentStatus, SubscriptionStatus
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


async def list_message_recipient_telegram_ids(
    session: AsyncSession,
    message: Message,
) -> list[int]:
    bundle_strategy_ids = await _bundle_strategy_ids_for_message(session, message)
    query = (
        select(Subscription, SubscriptionProduct, User.telegram_user_id)
        .join(User, Subscription.user_id == User.id)
        .join(SubscriptionProduct, Subscription.product_id == SubscriptionProduct.id)
        .where(
            User.telegram_user_id.is_not(None),
            Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
        )
    )
    result = await session.execute(query)
    recipients: set[int] = set()
    for _subscription, product, telegram_user_id in result.all():
        if telegram_user_id is None:
            continue
        if _subscription_matches_message(message, product=product, bundle_strategy_ids=bundle_strategy_ids):
            recipients.add(int(telegram_user_id))
    return sorted(recipients)


async def _bundle_strategy_ids_for_message(session: AsyncSession, message: Message) -> set[str]:
    if message.strategy_id is None:
        return set()
    query = select(BundleMember.bundle_id).where(BundleMember.strategy_id == message.strategy_id)
    result = await session.execute(query)
    bundle_ids = [item for item in result.scalars().all() if item is not None]
    if not bundle_ids:
        return set()
    bundle_result = await session.execute(select(BundleMember.strategy_id).where(BundleMember.bundle_id.in_(bundle_ids)))
    return {item for item in bundle_result.scalars().all() if item is not None}


def _subscription_matches_message(
    message: Message,
    *,
    product: SubscriptionProduct,
    bundle_strategy_ids: set[str],
) -> bool:
    deliver = {str(item).strip() for item in (message.deliver or []) if str(item).strip()}
    if not deliver:
        return False
    if MessageDeliver.STRATEGY.value in deliver and product.strategy_id == message.strategy_id:
        return True
    if MessageDeliver.AUTHOR.value in deliver and product.author_id == message.author_id:
        return True
    if MessageDeliver.BUNDLE.value in deliver and product.bundle_id is not None and message.strategy_id in bundle_strategy_ids:
        return True
    return False


def build_message_notification_text(message: Message) -> str:
    title = message.title or (message.strategy.title if message.strategy is not None else "Публикация")
    text_payload = message.text or {}
    lines = [
        "<b>Новая публикация по вашей подписке</b>",
        f"<b>{escape(str(title))}</b>",
        f"Стратегия: {escape(message.strategy.title) if message.strategy is not None else 'не указана'}",
        f"Тип: {escape(str(message.kind))}",
    ]
    body = str(text_payload.get("body") or text_payload.get("plain") or "").strip()
    if body:
        lines.append(body)
    if message.documents:
        lines.append(f"Документов: {len(message.documents)}")
    if message.deals:
        first_deal = message.deals[0]
        lines.append(
            "Deal: "
            f"{escape(str(first_deal.get('ticker') or first_deal.get('instrument') or first_deal.get('instrument_id') or 'инструмент'))} "
            f"{escape(str(first_deal.get('side') or 'n/a'))} "
            f"{escape(str(first_deal.get('price') or first_deal.get('entry_from') or 'n/a'))}"
        )
    return "\n".join(lines)


async def get_message_for_notification(
    session: AsyncSession,
    message_id: str,
) -> Message | None:
    query = (
        select(Message)
        .options(
            selectinload(Message.strategy),
            selectinload(Message.author),
            selectinload(Message.bundle),
            selectinload(Message.user),
            selectinload(Message.moderator),
        )
        .where(Message.id == message_id)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def deliver_message_notifications_by_id(
    session: AsyncSession,
    message_id: str,
    notifier,
    *,
    trigger: str = "publish",
    attempts: int = DEFAULT_NOTIFICATION_ATTEMPTS,
) -> list[int] | None:
    message = await get_message_for_notification(session, message_id)
    if message is None:
        return None
    return await deliver_message_notifications(
        session,
        message,
        notifier,
        trigger=trigger,
        attempts=attempts,
    )


async def deliver_message_notifications(
    session: AsyncSession,
    message: Message,
    notifier,
    *,
    trigger: str = "publish",
    attempts: int = DEFAULT_NOTIFICATION_ATTEMPTS,
) -> list[int]:
    recipients = await list_message_recipient_telegram_ids(session, message)

    # P3.4: Log delivery information
    logger.info("Delivery for message %s: found %d recipients", message.id, len(recipients))
    if len(recipients) == 0:
        logger.warning(
            "No recipients for message %s (strategy=%s): no active subscriptions with telegram_user_id",
            message.id,
            message.strategy_id,
        )

    text = build_message_notification_text(message)
    delivered: list[int] = []
    for chat_id in recipients:
        if await _send_with_retry(notifier.send_message, chat_id, text, attempts=attempts):
            delivered.append(chat_id)

    session.add(
        AuditEvent(
            actor_user_id=None,
            entity_type="message",
            entity_id=message.id,
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


async def deliver_message_notifications_file(
    graph: FileDatasetGraph,
    store: FileDataStore,
    message: Message,
    notifier,
    *,
    trigger: str = "publish",
    attempts: int = DEFAULT_NOTIFICATION_ATTEMPTS,
) -> list[int]:
    bundle_ids = {
        subscription.product.bundle_id
        for subscription in graph.subscriptions.values()
        if subscription.status in ACTIVE_SUBSCRIPTION_STATUSES
        and subscription.product is not None
        and subscription.product.bundle_id is not None
    }
    bundle_strategy_ids = {
        member.strategy_id
        for member in graph.bundle_members
        if member.bundle_id in bundle_ids
    }
    recipients = {
        subscription.user.telegram_user_id
        for subscription in graph.subscriptions.values()
        if subscription.status in ACTIVE_SUBSCRIPTION_STATUSES
        and subscription.user.telegram_user_id is not None
        and subscription.product is not None
        and _subscription_matches_message(
            message,
            product=subscription.product,
            bundle_strategy_ids=bundle_strategy_ids,
        )
    }
    text = build_message_notification_text(message)
    delivered: list[int] = []
    for chat_id in sorted(int(item) for item in recipients if item is not None):
        if await _send_with_retry(notifier.send_message, chat_id, text, attempts=attempts):
            delivered.append(chat_id)

    graph.add(
        AuditEvent(
            actor_user_id=None,
            entity_type="message",
            entity_id=message.id,
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
            "Failed to deliver message notification to chat_id=%s attempt=%s/%s",
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
    preferences = await _load_reminder_preferences_db(session)
    subscriptions = await _list_db_subscription_reminders(session, now=now)
    payments = await _list_db_payment_reminders(session, now=now)

    for subscription in subscriptions:
        if not preferences.get(subscription.user_id, {}).get("subscription_reminders", True):
            stats.skipped += 1
            continue
        key = _subscription_reminder_key(subscription)
        if key in sent_keys:
            stats.skipped += 1
            continue
        text = _build_subscription_reminder_text(subscription)
        if await _send_with_retry(notifier.send_message, int(subscription.user.telegram_user_id), text, attempts=attempts):
            session.add(
                _build_reminder_event(
                    "subscription",
                    subscription.id,
                    key,
                    "subscription_expiring",
                    user_id=subscription.user_id,
                    title=subscription.product.title if subscription.product is not None else "Подписка",
                )
            )
            sent_keys.add(key)
            stats.sent += 1

    for payment in payments:
        if not preferences.get(payment.user_id, {}).get("payment_reminders", True):
            stats.skipped += 1
            continue
        key = _payment_reminder_key(payment)
        if key in sent_keys:
            stats.skipped += 1
            continue
        text = _build_payment_reminder_text(payment)
        if await _send_with_retry(notifier.send_message, int(payment.user.telegram_user_id), text, attempts=attempts):
            session.add(
                _build_reminder_event(
                    "payment",
                    payment.id,
                    key,
                    "payment_pending",
                    user_id=payment.user_id,
                    title=payment.product.title if payment.product is not None else "Оплата",
                )
            )
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
    preferences = _load_reminder_preferences_file(graph)

    for subscription in _list_file_subscription_reminders(graph, now=now):
        if not preferences.get(subscription.user_id, {}).get("subscription_reminders", True):
            stats.skipped += 1
            continue
        key = _subscription_reminder_key(subscription)
        if key in sent_keys:
            stats.skipped += 1
            continue
        text = _build_subscription_reminder_text(subscription)
        if await _send_with_retry(notifier.send_message, int(subscription.user.telegram_user_id), text, attempts=attempts):
            graph.add(
                _build_reminder_event(
                    "subscription",
                    subscription.id,
                    key,
                    "subscription_expiring",
                    user_id=subscription.user_id,
                    title=subscription.product.title if subscription.product is not None else "Подписка",
                )
            )
            sent_keys.add(key)
            stats.sent += 1

    for payment in _list_file_payment_reminders(graph, now=now):
        if not preferences.get(payment.user_id, {}).get("payment_reminders", True):
            stats.skipped += 1
            continue
        key = _payment_reminder_key(payment)
        if key in sent_keys:
            stats.skipped += 1
            continue
        text = _build_payment_reminder_text(payment)
        if await _send_with_retry(notifier.send_message, int(payment.user.telegram_user_id), text, attempts=attempts):
            graph.add(
                _build_reminder_event(
                    "payment",
                    payment.id,
                    key,
                    "payment_pending",
                    user_id=payment.user_id,
                    title=payment.product.title if payment.product is not None else "Оплата",
                )
            )
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


async def _load_reminder_preferences_db(session: AsyncSession) -> dict[str, dict[str, bool]]:
    query = (
        select(AuditEvent)
        .where(AuditEvent.action == "subscriber.notification_preferences")
        .order_by(AuditEvent.created_at.desc())
    )
    result = await session.execute(query)
    prefs: dict[str, dict[str, bool]] = {}
    for event in result.scalars().all():
        payload = event.payload or {}
        user_id = payload.get("user_id")
        if user_id is None or str(user_id) in prefs:
            continue
        prefs[str(user_id)] = {
            "payment_reminders": bool(payload.get("payment_reminders", True)),
            "subscription_reminders": bool(payload.get("subscription_reminders", True)),
        }
    return prefs


def _load_reminder_preferences_file(graph: FileDatasetGraph) -> dict[str, dict[str, bool]]:
    events = [
        event
        for event in graph.audit_events.values()
        if event.action == "subscriber.notification_preferences"
    ]
    events.sort(key=lambda event: event.created_at, reverse=True)
    prefs: dict[str, dict[str, bool]] = {}
    for event in events:
        payload = event.payload or {}
        user_id = payload.get("user_id")
        if user_id is None or str(user_id) in prefs:
            continue
        prefs[str(user_id)] = {
            "payment_reminders": bool(payload.get("payment_reminders", True)),
            "subscription_reminders": bool(payload.get("subscription_reminders", True)),
        }
    return prefs


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


def _build_reminder_event(
    entity_type: str,
    entity_id: str,
    reminder_key: str,
    reminder_kind: str,
    *,
    user_id: str,
    title: str,
) -> AuditEvent:
    return AuditEvent(
        actor_user_id=None,
        entity_type=entity_type,
        entity_id=entity_id,
        action="notification.reminder",
        payload={
            "user_id": user_id,
            "title": title,
            "reminder_key": reminder_key,
            "kind": reminder_kind,
        },
    )
