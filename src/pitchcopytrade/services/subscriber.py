from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote

from pitchcopytrade.auth.session import build_telegram_login_link_token
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.catalog import SubscriptionProduct
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


def build_subscriber_status_message(snapshot: SubscriberStatusSnapshot) -> str:
    lines = [
        "Статус подписчика PitchCopyTrade",
        f"Telegram: подключен как @{snapshot.user.username}" if snapshot.user.username else "Telegram: подключен",
        f"Доступ: {'активен' if snapshot.has_access else 'еще не активирован'}",
    ]

    if snapshot.active_subscriptions:
        lines.append("")
        lines.append("Активные подписки:")
        for subscription in snapshot.active_subscriptions[:3]:
            product_title = _product_title(subscription.product)
            end_at = subscription.end_at.strftime("%Y-%m-%d %H:%M") if subscription.end_at else "n/a"
            lines.append(f"- {product_title} до {end_at} [{subscription.status.value}]")

    if snapshot.pending_payments:
        lines.append("")
        lines.append("Ожидают подтверждения:")
        for payment in snapshot.pending_payments[:3]:
            product_title = _product_title(payment.product)
            lines.append(
                f"- {product_title} | {payment.final_amount_rub} RUB | {payment.stub_reference or payment.id}"
            )

    lines.append("")
    if snapshot.visible_recommendation_titles:
        lines.append(f"Доступных рекомендаций сейчас: {len(snapshot.visible_recommendation_titles)}")
        for title in snapshot.visible_recommendation_titles[:3]:
            lines.append(f"- {title}")
    else:
        lines.append("Доступных рекомендаций сейчас: 0")

    lines.append("")
    lines.append("Команды:")
    lines.append("/catalog - витрина стратегий")
    lines.append("/feed - открыть рекомендации")
    lines.append("/web - подтвердить web fallback через Telegram")
    return "\n".join(lines)


def build_subscriber_web_message(user: User, *, base_url: str, include_webapp: bool) -> str:
    token = build_telegram_login_link_token(user)
    status_link = f"{base_url}/tg-auth?token={token}&next={quote('/app/status', safe='/')}"
    feed_link = f"{base_url}/tg-auth?token={token}&next={quote('/app/feed', safe='/')}"
    lines = [
        "Верификация через Telegram готова.",
        "Откройте эту ссылку, чтобы войти в web fallback без пароля и сначала увидеть статус доступа:",
        status_link,
        "",
        "Если нужно сразу открыть рекомендации, используйте прямую ссылку на feed:",
        feed_link,
    ]
    if include_webapp:
        lines.append("")
        lines.append("Mini App тоже доступен в меню бота.")
        lines.append(f"{base_url}/miniapp")
    return "\n".join(lines)


def _product_title(product: SubscriptionProduct | None) -> str:
    if product is None:
        return "Продукт"
    return product.title
