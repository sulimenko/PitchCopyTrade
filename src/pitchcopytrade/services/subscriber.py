from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.commerce import Payment, Subscription
from pitchcopytrade.db.models.enums import BillingPeriod, PaymentStatus, SubscriptionStatus
from pitchcopytrade.repositories.contracts import AccessRepository, PublicRepository
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
        visible_recommendation_titles=visible_titles,
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
