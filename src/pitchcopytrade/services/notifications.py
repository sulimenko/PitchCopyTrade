from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.audit import AuditEvent
from pitchcopytrade.db.models.catalog import BundleMember, SubscriptionProduct
from pitchcopytrade.db.models.commerce import Payment, Subscription
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.enums import MessageDeliver, MessageStatus, PaymentStatus, SubscriptionStatus
from pitchcopytrade.db.models.notification_log import NotificationChannelEnum, NotificationLog
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore
from pitchcopytrade.services.email_transport import send_smtp_email
from pitchcopytrade.services.message_rendering import render_message_email_text, render_message_notification_text


logger = logging.getLogger(__name__)
ACTIVE_SUBSCRIPTION_STATUSES = (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL)
DEFAULT_NOTIFICATION_ATTEMPTS = 3
SUBSCRIPTION_REMINDER_WINDOW = timedelta(days=3)
PAYMENT_REMINDER_WINDOW = timedelta(hours=6)


@dataclass(slots=True)
class ReminderStats:
    sent: int = 0
    skipped: int = 0


@dataclass(slots=True, frozen=True)
class RecipientSelectionDiagnostics:
    active_subscriptions: int
    telegram_bound_active_subscriptions: int
    matching_active_subscriptions: int
    reason: str


@dataclass(slots=True, frozen=True)
class MessageRecipient:
    user_id: str
    telegram_user_id: int | None
    email: str | None


async def list_message_recipient_telegram_ids(
    session: AsyncSession,
    message: Message,
) -> list[int]:
    recipients, _diagnostics = await _collect_message_recipients_db(session, message)
    return [item.telegram_user_id for item in recipients if item.telegram_user_id is not None]


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
    return render_message_notification_text(message)


def build_message_email_text(message: Message) -> str:
    return render_message_email_text(message)


def _message_title(message: Message) -> str:
    if message.title:
        return message.title
    if message.strategy is not None and message.strategy.title:
        return message.strategy.title
    return "Публикация"


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
    recipients, diagnostics = await _collect_message_recipients_db(session, message)
    return await _deliver_message_notifications_db(
        session,
        message,
        notifier,
        recipients,
        diagnostics,
        trigger=trigger,
        attempts=attempts,
    )


async def deliver_message_notifications_file(
    graph: FileDatasetGraph,
    store: FileDataStore,
    message: Message,
    notifier,
    *,
    trigger: str = "publish",
    attempts: int = DEFAULT_NOTIFICATION_ATTEMPTS,
) -> list[int]:
    recipients, diagnostics = _collect_message_recipients_file(graph, message)
    return await _deliver_message_notifications_file(
        graph,
        store,
        message,
        notifier,
        recipients,
        diagnostics,
        trigger=trigger,
        attempts=attempts,
    )


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


async def _deliver_message_notifications_db(
    session: AsyncSession,
    message: Message,
    notifier,
    recipients: list[MessageRecipient],
    diagnostics: RecipientSelectionDiagnostics,
    *,
    trigger: str,
    attempts: int,
) -> list[int]:
    return await _deliver_message_notifications_runtime(
        message=message,
        recipients=recipients,
        diagnostics=diagnostics,
        send_telegram=notifier.send_message,
        send_email_subject=f"Новая публикация: {_message_title(message)}",
        send_email_body=build_message_email_text(message),
        admin_email=get_settings().admin_email,
        attempts=attempts,
        trigger=trigger,
        append_notification_log=lambda log: session.add(log),
        append_audit_event=lambda event: session.add(event),
        finalize=session.commit,
    )


async def _deliver_message_notifications_file(
    graph: FileDatasetGraph,
    store: FileDataStore,
    message: Message,
    notifier,
    recipients: list[MessageRecipient],
    diagnostics: RecipientSelectionDiagnostics,
    *,
    trigger: str,
    attempts: int,
) -> list[int]:
    return await _deliver_message_notifications_runtime(
        message=message,
        recipients=recipients,
        diagnostics=diagnostics,
        send_telegram=notifier.send_message,
        send_email_subject=f"Новая публикация: {_message_title(message)}",
        send_email_body=build_message_email_text(message),
        admin_email=get_settings().admin_email,
        attempts=attempts,
        trigger=trigger,
        append_notification_log=lambda log: graph.add(log),
        append_audit_event=lambda event: graph.add(event),
        finalize=lambda: graph.save(store),
    )


async def _deliver_message_notifications_runtime(
    *,
    message: Message,
    recipients: list[MessageRecipient],
    diagnostics: RecipientSelectionDiagnostics,
    send_telegram: Callable[[int, str], Awaitable[object]],
    send_email_subject: str,
    send_email_body: str,
    admin_email: str | None,
    attempts: int,
    trigger: str,
    append_notification_log: Callable[[NotificationLog], None],
    append_audit_event: Callable[[AuditEvent], None],
    finalize: Callable[[], Awaitable[None] | None],
) -> list[int]:
    logger.info(
        "Message delivery for %s: recipients=%d active=%d tg_bound=%d matching=%d",
        message.id,
        len(recipients),
        diagnostics.active_subscriptions,
        diagnostics.telegram_bound_active_subscriptions,
        diagnostics.matching_active_subscriptions,
    )
    if not recipients:
        logger.warning(
            (
                "No recipients for message %s (strategy=%s): %s; "
                "active_subscriptions=%d; telegram_bound_active_subscriptions=%d; matching_active_subscriptions=%d"
            ),
            message.id,
            message.strategy_id,
            diagnostics.reason,
            diagnostics.active_subscriptions,
            diagnostics.telegram_bound_active_subscriptions,
            diagnostics.matching_active_subscriptions,
        )

    telegram_text = build_message_notification_text(message)
    delivered_telegram_ids: list[int] = []
    telegram_success_count = 0
    email_success_count = 0
    telegram_failure_count = 0
    email_failure_count = 0
    fallback_email_attempted = 0
    missing_telegram_id_count = 0
    missing_email_count = 0
    telegram_transport_failure_count = 0
    smtp_not_configured_count = 0
    smtp_transport_failure_count = 0
    admin_copy_sent = False

    for recipient in recipients:
        telegram_sent = False
        telegram_error_detail: str | None = None
        if recipient.telegram_user_id is not None:
            logger.info(
                "Message delivery primary telegram attempt: message=%s user_id=%s telegram_user_id=%s",
                message.id,
                recipient.user_id,
                recipient.telegram_user_id,
            )
            telegram_sent = await _send_with_retry(send_telegram, recipient.telegram_user_id, telegram_text, attempts=attempts)
            if telegram_sent:
                telegram_success_count += 1
                delivered_telegram_ids.append(recipient.telegram_user_id)
            else:
                telegram_failure_count += 1
                telegram_transport_failure_count += 1
                telegram_error_detail = "telegram transport failure"
        else:
            telegram_failure_count += 1
            missing_telegram_id_count += 1
            telegram_error_detail = "no telegram_user_id"

        append_notification_log(
            NotificationLog(
                message_id=message.id,
                user_id=recipient.user_id,
                channel=NotificationChannelEnum.TELEGRAM,
                sent_at=datetime.now(timezone.utc) if telegram_sent else None,
                success=telegram_sent,
                error_detail=telegram_error_detail,
            )
        )

        if telegram_sent:
            continue

        if recipient.email is None:
            logger.warning(
                "Message delivery fallback skipped: message=%s user_id=%s reason=no email",
                message.id,
                recipient.user_id,
            )
            email_failure_count += 1
            missing_email_count += 1
            append_notification_log(
                NotificationLog(
                    message_id=message.id,
                    user_id=recipient.user_id,
                    channel=NotificationChannelEnum.EMAIL,
                    sent_at=None,
                    success=False,
                    error_detail="email not set",
                )
            )
            continue

        fallback_email_attempted += 1
        logger.info(
            "Message delivery fallback email attempt: message=%s user_id=%s email=%s admin_copy=%s",
            message.id,
            recipient.user_id,
            recipient.email,
            bool(admin_email),
        )
        email_sent, email_error = await send_smtp_email(
            to_email=recipient.email,
            subject=send_email_subject,
            body=send_email_body,
            bcc_emails=(admin_email,) if admin_email else (),
        )
        admin_copy_sent = admin_copy_sent or (email_sent and bool(admin_email))
        if email_sent:
            email_success_count += 1
        else:
            email_failure_count += 1
            if email_error == "smtp is not configured":
                smtp_not_configured_count += 1
            else:
                smtp_transport_failure_count += 1
        append_notification_log(
            NotificationLog(
                message_id=message.id,
                user_id=recipient.user_id,
                channel=NotificationChannelEnum.EMAIL,
                sent_at=datetime.now(timezone.utc) if email_sent else None,
                success=email_sent,
                error_detail=email_error,
            )
        )

    append_audit_event(
        AuditEvent(
            actor_user_id=None,
            entity_type="message",
            entity_id=message.id,
            action="notification.delivery",
            payload={
                "recipient_count": telegram_success_count + email_success_count,
                "attempted_count": len(recipients),
                "telegram_success_count": telegram_success_count,
                "telegram_failure_count": telegram_failure_count,
                "email_attempted_count": fallback_email_attempted,
                "email_success_count": email_success_count,
                "email_failure_count": email_failure_count,
                "missing_telegram_id_count": missing_telegram_id_count,
                "missing_email_count": missing_email_count,
                "telegram_transport_failure_count": telegram_transport_failure_count,
                "smtp_not_configured_count": smtp_not_configured_count,
                "smtp_transport_failure_count": smtp_transport_failure_count,
                "trigger": trigger,
                "attempts": attempts,
                "primary_channel": "telegram",
                "fallback_channel": "email",
                "admin_copy_sent": admin_copy_sent,
                "admin_email_configured": bool(admin_email),
            },
        )
    )
    result = finalize()
    if hasattr(result, "__await__"):
        await result
    return delivered_telegram_ids


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


async def _collect_message_recipients_db(
    session: AsyncSession,
    message: Message,
) -> tuple[list[MessageRecipient], RecipientSelectionDiagnostics]:
    bundle_strategy_ids = await _bundle_strategy_ids_for_message(session, message)
    query = (
        select(Subscription, SubscriptionProduct, User.telegram_user_id)
        .options(selectinload(Subscription.user))
        .join(User, Subscription.user_id == User.id)
        .join(SubscriptionProduct, Subscription.product_id == SubscriptionProduct.id)
        .where(Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES))
    )
    result = await session.execute(query)
    recipients: dict[str, MessageRecipient] = {}
    active_subscriptions = 0
    telegram_bound_active_subscriptions = 0
    matching_active_subscriptions = 0
    for subscription, product, telegram_user_id in result.all():
        active_subscriptions += 1
        if telegram_user_id is not None:
            telegram_bound_active_subscriptions += 1
        if _subscription_matches_message(message, product=product, bundle_strategy_ids=bundle_strategy_ids):
            matching_active_subscriptions += 1
            user = subscription.user
            if user is not None:
                recipients.setdefault(
                    user.id,
                    MessageRecipient(
                        user_id=user.id,
                        telegram_user_id=int(telegram_user_id) if telegram_user_id is not None else None,
                        email=user.email,
                    ),
                )
    diagnostics = RecipientSelectionDiagnostics(
        active_subscriptions=active_subscriptions,
        telegram_bound_active_subscriptions=telegram_bound_active_subscriptions,
        matching_active_subscriptions=matching_active_subscriptions,
        reason=_recipient_selection_reason(
            active_subscriptions=active_subscriptions,
            telegram_bound_active_subscriptions=telegram_bound_active_subscriptions,
            matching_active_subscriptions=matching_active_subscriptions,
        ),
    )
    return sorted(recipients.values(), key=lambda item: (item.telegram_user_id or 0, item.user_id)), diagnostics


def _collect_message_recipients_file(
    graph: FileDatasetGraph,
    message: Message,
) -> tuple[list[MessageRecipient], RecipientSelectionDiagnostics]:
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
    recipients: dict[str, MessageRecipient] = {}
    active_subscriptions = 0
    telegram_bound_active_subscriptions = 0
    matching_active_subscriptions = 0
    for subscription in graph.subscriptions.values():
        if subscription.status not in ACTIVE_SUBSCRIPTION_STATUSES:
            continue
        active_subscriptions += 1
        if subscription.product is None:
            continue
        if subscription.user.telegram_user_id is not None:
            telegram_bound_active_subscriptions += 1
        if _subscription_matches_message(
            message,
            product=subscription.product,
            bundle_strategy_ids=bundle_strategy_ids,
        ):
            matching_active_subscriptions += 1
            recipients.setdefault(
                subscription.user.id,
                MessageRecipient(
                    user_id=subscription.user.id,
                    telegram_user_id=int(subscription.user.telegram_user_id) if subscription.user.telegram_user_id is not None else None,
                    email=subscription.user.email,
                ),
            )
    diagnostics = RecipientSelectionDiagnostics(
        active_subscriptions=active_subscriptions,
        telegram_bound_active_subscriptions=telegram_bound_active_subscriptions,
        matching_active_subscriptions=matching_active_subscriptions,
        reason=_recipient_selection_reason(
            active_subscriptions=active_subscriptions,
            telegram_bound_active_subscriptions=telegram_bound_active_subscriptions,
            matching_active_subscriptions=matching_active_subscriptions,
        ),
    )
    return sorted(recipients.values(), key=lambda item: (item.telegram_user_id or 0, item.user_id)), diagnostics


def _recipient_selection_reason(
    *,
    active_subscriptions: int,
    telegram_bound_active_subscriptions: int,
    matching_active_subscriptions: int,
) -> str:
    if active_subscriptions == 0:
        return "no active subscriptions"
    if telegram_bound_active_subscriptions == 0:
        return "active subscriptions exist but none have telegram_user_id"
    if matching_active_subscriptions == 0:
        return "active subscriptions exist but do not match message audience"
    return "recipient selection returned zero recipients unexpectedly"


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
