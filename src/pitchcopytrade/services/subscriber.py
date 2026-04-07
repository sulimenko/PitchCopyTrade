from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.audit import AuditEvent
from pitchcopytrade.db.models.commerce import Payment, Subscription
from pitchcopytrade.db.models.enums import BillingPeriod, PaymentProvider, PaymentStatus, SubscriptionStatus
from pitchcopytrade.payments.tbank import TBankAcquiringClient
from pitchcopytrade.repositories.contracts import AccessRepository, PublicRepository
from pitchcopytrade.services.payment_sync import apply_tbank_state_to_payment, extract_provider_payment_id
from pitchcopytrade.services.acl import get_user_by_telegram_id, list_user_visible_recommendations, user_has_active_access


ACTIVE_SUBSCRIPTION_STATUSES = {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL}


@dataclass(slots=True)
class SubscriberStatusSnapshot:
    user: User
    has_access: bool
    subscriptions: list[Subscription]
    active_subscriptions: list[Subscription]
    payments: list[Payment]
    pending_payments: list[Payment]
    visible_message_titles: list[str]


@dataclass(slots=True, frozen=True)
class PaymentHistoryEntry:
    checked_at: str
    status: str
    payment_id: str | None


@dataclass(slots=True, frozen=True)
class NotificationPreferences:
    payment_reminders: bool
    subscription_reminders: bool


@dataclass(slots=True, frozen=True)
class ReminderEntry:
    created_at: str
    title: str
    kind: str


@dataclass(slots=True, frozen=True)
class TimelineEntry:
    happened_at: str
    title: str
    detail: str
    category: str


@dataclass(slots=True, frozen=True)
class ActionCard:
    title: str
    detail: str
    href: str
    action_label: str
    tone: str


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
    subscriptions = sorted(
        list(user.subscriptions or []),
        key=lambda item: item.updated_at or item.end_at or item.start_at or datetime.min,
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
    payments = sorted(
        list(user.payments or []),
        key=lambda item: item.updated_at or item.created_at or datetime.min,
        reverse=True,
    )
    visible_titles = [item.title or item.strategy.title for item in recommendations]
    return SubscriberStatusSnapshot(
        user=user,
        has_access=has_access,
        subscriptions=subscriptions,
        active_subscriptions=active_subscriptions,
        payments=payments,
        pending_payments=pending_payments,
        visible_message_titles=visible_titles,
    )


PAYMENT_STATUS_LABELS = {
    PaymentStatus.CREATED: "Создана",
    PaymentStatus.PENDING: "Ожидает оплаты",
    PaymentStatus.PAID: "Оплачена",
    PaymentStatus.FAILED: "Ошибка оплаты",
    PaymentStatus.EXPIRED: "Истек срок оплаты",
    PaymentStatus.CANCELLED: "Отменена",
    PaymentStatus.REFUNDED: "Возвращена",
}

SUBSCRIPTION_STATUS_LABELS = {
    SubscriptionStatus.PENDING: "Ожидает активации",
    SubscriptionStatus.TRIAL: "Пробный период",
    SubscriptionStatus.ACTIVE: "Активна",
    SubscriptionStatus.EXPIRED: "Истекла",
    SubscriptionStatus.CANCELLED: "Отменена",
    SubscriptionStatus.BLOCKED: "Заблокирована",
}

BILLING_PERIOD_LABELS = {
    BillingPeriod.MONTH: "Месяц",
    BillingPeriod.QUARTER: "Квартал",
    BillingPeriod.YEAR: "Год",
}


def payment_status_label(status: PaymentStatus) -> str:
    return PAYMENT_STATUS_LABELS.get(status, status.value)


def subscription_status_label(status: SubscriptionStatus) -> str:
    return SUBSCRIPTION_STATUS_LABELS.get(status, status.value)


def billing_period_label(period: BillingPeriod | None) -> str:
    if period is None:
        return "Период не указан"
    return BILLING_PERIOD_LABELS.get(period, period.value)


def payment_result_message(payment: Payment) -> str:
    if payment.status is PaymentStatus.PAID:
        return "Оплата подтверждена. Доступ к публикациям уже активирован или будет активирован в ближайший момент."
    if payment.status is PaymentStatus.PENDING:
        return "Платеж еще обрабатывается. Вы можете открыть оплату, обновить статус или дождаться автоматической синхронизации."
    if payment.status is PaymentStatus.FAILED:
        return "Платеж завершился ошибкой. Попробуйте снова запустить оплату из этой карточки."
    if payment.status is PaymentStatus.EXPIRED:
        return "Срок этой оплаты истек. Можно сразу создать новую попытку оплаты."
    if payment.status is PaymentStatus.CANCELLED:
        return "Эта заявка отменена. При необходимости создайте новую попытку оплаты."
    if payment.status is PaymentStatus.REFUNDED:
        return "По этой оплате оформлен возврат."
    return "Статус оплаты обновлен."


def payment_history(payment: Payment) -> list[PaymentHistoryEntry]:
    payload = payment.provider_payload or {}
    history = payload.get("state_history", [])
    items: list[PaymentHistoryEntry] = []
    for entry in reversed(history):
        if not isinstance(entry, dict):
            continue
        items.append(
            PaymentHistoryEntry(
                checked_at=str(entry.get("checked_at") or "не указано"),
                status=str(entry.get("status") or "unknown"),
                payment_id=str(entry.get("payment_id")) if entry.get("payment_id") is not None else None,
            )
        )
    return items


def subscription_renewal_history(snapshot: SubscriberStatusSnapshot, subscription: Subscription) -> list[Subscription]:
    product_id = subscription.product.id
    if product_id is None:
        return []
    return [
        item
        for item in snapshot.subscriptions
        if item.product.id == product_id and item.id != subscription.id
    ]


async def get_notification_preferences(
    repository: AccessRepository,
    *,
    user_id: str,
) -> NotificationPreferences:
    payload = await repository.get_notification_preferences(user_id=user_id)
    return NotificationPreferences(
        payment_reminders=bool(payload.get("payment_reminders", True)),
        subscription_reminders=bool(payload.get("subscription_reminders", True)),
    )


async def update_notification_preferences(
    repository: AccessRepository,
    *,
    user_id: str,
    payment_reminders: bool,
    subscription_reminders: bool,
) -> NotificationPreferences:
    payload = await repository.save_notification_preferences(
        user_id=user_id,
        preferences={
            "payment_reminders": payment_reminders,
            "subscription_reminders": subscription_reminders,
        },
    )
    return NotificationPreferences(
        payment_reminders=bool(payload.get("payment_reminders", True)),
        subscription_reminders=bool(payload.get("subscription_reminders", True)),
    )


async def list_reminder_center_entries(
    repository: AccessRepository,
    *,
    user_id: str,
    limit: int = 20,
) -> list[ReminderEntry]:
    events = await repository.list_user_reminder_events(user_id=user_id, limit=limit)
    return [_reminder_entry_from_event(item) for item in events]


def build_subscriber_timeline(snapshot: SubscriberStatusSnapshot) -> list[TimelineEntry]:
    items: list[TimelineEntry] = []
    for payment in snapshot.payments:
        items.append(
            TimelineEntry(
                happened_at=str(payment.created_at or "не указано"),
                title=f"Оплата: {payment.product.title if payment.product else 'Продукт'}",
                detail=payment_status_label(payment.status),
                category="payment",
            )
        )
        for event in payment_history(payment):
            items.append(
                TimelineEntry(
                    happened_at=event.checked_at,
                    title=f"Статус оплаты: {payment.product.title if payment.product else 'Продукт'}",
                    detail=event.status,
                    category="payment_state",
                )
            )
    for subscription in snapshot.subscriptions:
        items.append(
            TimelineEntry(
                happened_at=str(subscription.start_at or "не указано"),
                title=f"Подписка: {subscription.product.title if subscription.product else 'Продукт'}",
                detail=subscription_status_label(subscription.status),
                category="subscription",
            )
        )
        if subscription.end_at is not None:
            items.append(
                TimelineEntry(
                    happened_at=str(subscription.end_at),
                    title=f"Окончание подписки: {subscription.product.title if subscription.product else 'Продукт'}",
                    detail="Плановая дата окончания",
                    category="subscription_end",
                )
            )
    items.sort(key=lambda item: item.happened_at, reverse=True)
    return items


def build_action_cards(snapshot: SubscriberStatusSnapshot) -> list[ActionCard]:
    cards: list[ActionCard] = []
    for payment in snapshot.pending_payments[:2]:
        cards.append(
            ActionCard(
                title=f"Завершите оплату: {payment.product.title if payment.product else 'Подписка'}",
                detail=f"{payment.final_amount_rub} руб · {payment_status_label(payment.status)}",
                href=f"/app/payments/{payment.id}",
                action_label="Открыть оплату",
                tone="warning",
            )
        )
    expiring = sorted(
        [
            item
            for item in snapshot.active_subscriptions
            if item.end_at is not None
        ],
        key=lambda item: item.end_at,
    )
    for subscription in expiring[:2]:
        cards.append(
            ActionCard(
                title=f"Продлите доступ: {subscription.product.title if subscription.product else 'Подписка'}",
                detail=f"Окончание: {subscription.end_at}",
                href=f"/app/subscriptions/{subscription.id}",
                action_label="Открыть подписку",
                tone="info",
            )
        )
    if not cards:
        cards.append(
            ActionCard(
                title="Mini App готов к работе",
                detail="Каталог, оплаты, подписки и лента доступны в одном контуре без отдельного входа.",
                href="/app/catalog",
                action_label="Открыть каталог",
                tone="neutral",
            )
        )
    return cards


def _reminder_entry_from_event(event: AuditEvent) -> ReminderEntry:
    payload = event.payload or {}
    kind = str(payload.get("kind") or "reminder")
    title = str(payload.get("title") or "Напоминание")
    return ReminderEntry(
        created_at=str(event.created_at or "не указано"),
        title=title,
        kind="Оплата" if kind == "payment_pending" else "Подписка" if kind == "subscription_expiring" else kind,
    )


async def cancel_pending_payment(
    repository: PublicRepository,
    *,
    telegram_user_id: int,
    payment_id: str,
) -> Payment | None:
    payment = await repository.get_user_payment(telegram_user_id=telegram_user_id, payment_id=payment_id)
    if payment is None or payment.status is not PaymentStatus.PENDING:
        return None
    payment.status = PaymentStatus.CANCELLED
    for subscription in payment.subscriptions:
        if subscription.status is SubscriptionStatus.PENDING:
            subscription.status = SubscriptionStatus.CANCELLED
    await repository.commit()
    await repository.refresh(payment)
    return payment


async def toggle_subscription_autorenew(
    repository: PublicRepository,
    *,
    telegram_user_id: int,
    subscription_id: str,
    enabled: bool,
) -> Subscription | None:
    subscription = await repository.get_user_subscription(
        telegram_user_id=telegram_user_id,
        subscription_id=subscription_id,
    )
    if subscription is None or subscription.status in {SubscriptionStatus.CANCELLED, SubscriptionStatus.BLOCKED}:
        return None
    subscription.autorenew_enabled = enabled
    await repository.commit()
    await repository.refresh(subscription)
    return subscription


async def refresh_pending_payment(
    repository: PublicRepository,
    *,
    telegram_user_id: int,
    payment_id: str,
    now: datetime | None = None,
) -> Payment | None:
    payment = await repository.get_user_payment(telegram_user_id=telegram_user_id, payment_id=payment_id)
    if payment is None or payment.status is not PaymentStatus.PENDING or payment.provider is not PaymentProvider.TBANK:
        return payment

    provider_payment_id = extract_provider_payment_id(payment)
    if not provider_payment_id:
        return payment

    settings = get_settings()
    client = TBankAcquiringClient(
        terminal_key=settings.payments.tinkoff_terminal_key.get_secret_value(),
        password=settings.payments.tinkoff_secret_key.get_secret_value(),
    )
    state = await client.get_state(payment_id=provider_payment_id)
    provider_status = str(state.get("Status") or "").upper()
    apply_tbank_state_to_payment(payment, state, provider_status=provider_status, timestamp=now or datetime.now(timezone.utc))
    await repository.commit()
    await repository.refresh(payment)
    return payment


async def retry_payment_checkout(
    repository: PublicRepository,
    *,
    telegram_user_id: int,
    payment_id: str,
    promo_code_value: str | None = None,
):
    payment = await repository.get_user_payment(telegram_user_id=telegram_user_id, payment_id=payment_id)
    user = await repository.get_user_by_telegram_id(telegram_user_id)
    if payment is None or user is None or payment.product is None:
        return None
    if payment.status not in {PaymentStatus.FAILED, PaymentStatus.EXPIRED, PaymentStatus.CANCELLED}:
        return None
    accepted_document_ids = await _accepted_active_document_ids(repository, user)
    from pitchcopytrade.services.public import TelegramSubscriberProfile, create_telegram_stub_checkout

    return await create_telegram_stub_checkout(
        repository,
        product=payment.product,
        profile=_build_profile_from_user(user),
        accepted_document_ids=accepted_document_ids,
        promo_code_value=promo_code_value or (payment.promo_code.code if payment.promo_code is not None else None),
    )


async def renew_subscription_checkout(
    repository: PublicRepository,
    *,
    telegram_user_id: int,
    subscription_id: str,
    promo_code_value: str | None = None,
):
    subscription = await repository.get_user_subscription(
        telegram_user_id=telegram_user_id,
        subscription_id=subscription_id,
    )
    user = await repository.get_user_by_telegram_id(telegram_user_id)
    if subscription is None or user is None or subscription.product is None:
        return None
    if subscription.status is SubscriptionStatus.PENDING:
        return None
    accepted_document_ids = await _accepted_active_document_ids(repository, user)
    from pitchcopytrade.services.public import create_telegram_stub_checkout

    return await create_telegram_stub_checkout(
        repository,
        product=subscription.product,
        profile=_build_profile_from_user(user),
        accepted_document_ids=accepted_document_ids,
        promo_code_value=promo_code_value
        or (subscription.applied_promo_code.code if subscription.applied_promo_code is not None else None),
    )


async def cancel_subscription(
    repository: PublicRepository,
    *,
    telegram_user_id: int,
    subscription_id: str,
    now: datetime | None = None,
) -> Subscription | None:
    subscription = await repository.get_user_subscription(
        telegram_user_id=telegram_user_id,
        subscription_id=subscription_id,
    )
    if subscription is None or subscription.status in {SubscriptionStatus.CANCELLED, SubscriptionStatus.BLOCKED}:
        return None
    timestamp = now or datetime.now(timezone.utc)
    subscription.status = SubscriptionStatus.CANCELLED
    subscription.autorenew_enabled = False
    if subscription.end_at is None or subscription.end_at > timestamp:
        subscription.end_at = timestamp
    payment = subscription.payment
    if payment is not None and payment.status is PaymentStatus.PENDING:
        payment.status = PaymentStatus.CANCELLED
    await repository.commit()
    await repository.refresh(subscription)
    return subscription


def _build_profile_from_user(user: User):
    from pitchcopytrade.services.public import TelegramSubscriberProfile

    if user.telegram_user_id is None:
        raise ValueError("Telegram ID не найден. Пожалуйста, откройте Mini App заново.")
    return TelegramSubscriberProfile(
        telegram_user_id=user.telegram_user_id,
        username=user.username,
        first_name=None,
        last_name=None,
        full_name=user.full_name,
        email=user.email,
        timezone_name=user.timezone or "Europe/Moscow",
        lead_source_name="telegram_miniapp",
    )


async def _accepted_active_document_ids(repository: PublicRepository, user: User) -> list[str]:
    from pitchcopytrade.services.public import list_active_checkout_documents

    documents = await list_active_checkout_documents(repository)
    accepted_ids = {
        consent.document_id
        for consent in (user.consents or [])
        if consent.document_id is not None
    }
    required_ids = [document.id for document in documents]
    missing_ids = [item for item in required_ids if item not in accepted_ids]
    if missing_ids:
        raise ValueError("Для повторной оплаты нужно заново открыть оформление и принять актуальные документы")
    return required_ids
