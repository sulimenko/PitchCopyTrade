from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value or ""))


def _label(value: object, mapping: dict[str, str]) -> str:
    raw = _enum_value(value)
    return mapping.get(raw, raw)


def label_role(value: object) -> str:
    return _label(value, {"admin": "Администратор", "author": "Автор", "moderator": "Модератор"})


def label_user_status(value: object) -> str:
    return _label(value, {"invited": "Приглашён", "active": "Активен", "inactive": "отключён"})


def label_invite_delivery_status(value: object) -> str:
    return _label(value, {"sent": "Отправлено", "failed": "Ошибка отправки", "resent": "Отправлено повторно"})


def label_strategy_status(value: object) -> str:
    return _label(value, {"draft": "Черновик", "published": "Опубликована", "archived": "В архиве"})


def label_risk_level(value: object) -> str:
    return _label(value, {"low": "Низкий", "medium": "Средний", "high": "Высокий"})


def label_product_type(value: object) -> str:
    return _label(value, {"strategy": "Стратегия", "author": "Автор", "bundle": "Пакет"})


def label_duration_days(value: object) -> str:
    raw = getattr(value, "duration_days", value)
    if hasattr(raw, "value"):
        raw = getattr(raw, "value")
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return "Период не указан"
    return {30: "30 дней", 60: "60 дней", 90: "90 дней", 180: "180 дней", 365: "1 год"}.get(days, f"{days} дней")


def label_payment_provider(value: object) -> str:
    return _label(value, {"stub_manual": "Ручной платёж", "tbank": "Т-Банк"})


def label_payment_status(value: object) -> str:
    return _label(
        value,
        {
            "created": "Создан",
            "pending": "В ожидании",
            "paid": "Оплачен",
            "failed": "Ошибка",
            "expired": "Истёк",
            "cancelled": "Отменён",
            "refunded": "Возвращён",
        },
    )


def label_subscription_status(value: object) -> str:
    return _label(
        value,
        {
            "pending": "В ожидании",
            "trial": "Пробная",
            "active": "Активна",
            "expired": "Истекла",
            "cancelled": "Отменена",
            "blocked": "Заблокирована",
        },
    )


def label_message_kind(value: object) -> str:
    return _label(value, {"new_idea": "Новая идея", "update": "Обновление", "close": "Закрытие", "cancel": "Отмена"})


def label_message_status(value: object) -> str:
    return _label(
        value,
        {
            "draft": "Черновик",
            "review": "На модерации",
            "approved": "Одобрено",
            "scheduled": "Запланировано",
            "published": "Опубликовано",
            "closed": "Закрыто",
            "cancelled": "Отменено",
            "archived": "В архиве",
        },
    )


def label_trade_side(value: object) -> str:
    return _label(value, {"buy": "Покупка", "sell": "Продажа"})


def label_legal_document_type(value: object) -> str:
    return _label(
        value,
        {
            "disclaimer": "Дисклеймер",
            "offer": "Оферта",
            "privacy_policy": "Политика конфиденциальности",
            "payment_consent": "Согласие на оплату",
        },
    )


def label_sla_state(value: object) -> str:
    return _label(value, {"ok": "В норме", "warning": "Риск", "breach": "Нарушен"})


def label_audit_action(value: object) -> str:
    return _label(
        value,
        {
            "moderation.approve": "Одобрено модератором",
            "moderation.rework": "Возвращено на доработку",
            "moderation.reject": "Отклонено модератором",
            "worker.scheduled_publish": "Отложенная публикация",
            "notification.delivery": "Доставка уведомления",
            "notification.reminder": "Напоминание",
            "payment.webhook_sync": "Синхронизация платежа",
            "staff.activated": "Сотрудник активирован",
            "staff.deactivated": "Сотрудник деактивирован",
            "staff.admin_role_granted": "Выдана роль администратора",
            "staff.admin_role_revoked": "Снята роль администратора",
            "staff.invite_sent": "Отправлено приглашение",
            "subscriber.notification_preferences": "Изменены настройки уведомлений",
        },
    )


templates.env.globals.update(
    label_role=label_role,
    label_user_status=label_user_status,
    label_invite_delivery_status=label_invite_delivery_status,
    label_strategy_status=label_strategy_status,
    label_risk_level=label_risk_level,
    label_product_type=label_product_type,
    label_duration_days=label_duration_days,
    label_payment_provider=label_payment_provider,
    label_payment_status=label_payment_status,
    label_subscription_status=label_subscription_status,
    label_message_kind=label_message_kind,
    label_message_status=label_message_status,
    label_trade_side=label_trade_side,
    label_legal_document_type=label_legal_document_type,
    label_sla_state=label_sla_state,
    label_audit_action=label_audit_action,
)
