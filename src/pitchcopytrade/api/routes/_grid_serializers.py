"""
Serializers for Tabulator grid data.
Each function takes domain objects and returns JSON string.
"""
import json
from datetime import datetime
from typing import Any


def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.strftime("%d.%m.%Y %H:%M")


def _badge(text: str, cls: str = "") -> str:
    return f'<span class="staff-badge {cls}">{text}</span>'


def _link(url: str, text: str = "Открыть") -> str:
    return f'<a class="staff-btn ghost" href="{url}">{text}</a>'


def serialize_strategies(strategies: list, request_url_for=None) -> str:
    """Serialize strategies for admin grid."""
    data = []
    for item in strategies:
        risk_class = "ok" if item.risk == "low" else "warn" if item.risk == "medium" else "danger"
        status_class = "ok" if item.status == "active" else "warn"

        data.append({
            "strategy": f"<strong>{item.title}</strong><br><small>{item.slug}</small>",
            "author": item.author.display_name if item.author else "",
            "risk": _badge(item.risk.upper(), risk_class),
            "status": _badge(item.status.upper(), status_class),
            "is_public": "Да" if item.is_public else "Нет",
            "min_capital": f"{item.min_capital:,.0f}" if item.min_capital else "—",
            "actions": _link(f"/admin/strategies/{item.id}", "Открыть"),
        })
    return json.dumps(data, default=str)


def serialize_authors(authors: list, request_url_for=None) -> str:
    """Serialize authors for admin grid."""
    data = []
    for item in authors:
        status_class = "ok" if item.status == "active" else "warn" if item.status == "pending" else "danger"
        invite_status = ""
        if item.invite_token_version > 0:
            invite_status = _badge("Отправлено", "ok")
        elif item.invite_delivery_status == "FAILED":
            invite_status = _badge("Ошибка", "danger")

        actions_html = ""
        if hasattr(item, 'has_linked_user') and item.has_linked_user:
            actions_html = f'<button type="button" class="ghost" data-open-staff-dialog="author-edit-{item.id}">Редактировать</button>'
        else:
            actions_html = '<span class="muted">Недоступно</span>'

        data.append({
            "name": f"<strong>{item.display_name}</strong><br>{item.email}",
            "email": item.email,
            "telegram_id": str(item.telegram_id) if item.telegram_id else "—",
            "moderation": f'<form method="post" action="/admin/authors/{item.id}/moderation"><input type="checkbox" {"checked" if item.requires_moderation else ""} onchange="this.form.submit()"></form>',
            "status": _badge(item.status.upper(), status_class),
            "invite": invite_status,
            "actions": actions_html,
        })
    return json.dumps(data, default=str)


def serialize_staff(staff: list, current_user_id: str | None = None, request_url_for=None) -> str:
    """Serialize staff members for admin grid."""
    data = []
    for item in staff:
        roles_html = " ".join(_badge(role.name.upper(), "ok") for role in item.roles)
        status_class = "ok" if item.status == "active" else "danger"

        name_suffix = " <small>(это вы)</small>" if item.id == current_user_id else ""
        invite_status = ""
        if item.invite_token_version > 0:
            invite_status = _badge("Отправлено", "ok")
        elif item.invite_delivery_status == "FAILED":
            invite_status = _badge("Ошибка", "danger")

        data.append({
            "name": f"<strong>{item.display_name}</strong><br>{item.email}{name_suffix}",
            "roles": roles_html,
            "status": _badge(item.status.upper(), status_class),
            "invite": invite_status,
            "telegram_id": str(item.telegram_id) if item.telegram_id else "—",
            "actions": _link(f"/admin/staff/{item.id}", "Редактировать"),
        })
    return json.dumps(data, default=str)


def serialize_products(products: list, request_url_for=None) -> str:
    """Serialize products for admin grid."""
    data = []
    for item in products:
        status_badges = " ".join(_badge(s.upper(), "ok") for s in [item.status])

        data.append({
            "product": f"<strong>{item.title}</strong><br>{item.slug}",
            "type": item.kind.upper() if hasattr(item, 'kind') else item.type.upper() if hasattr(item, 'type') else "",
            "period": f"{item.period_days} дн" if item.period_days else "∞",
            "status": status_badges,
            "price": f"{item.price_rub:,.0f} ₽" if item.price_rub else "—",
            "trial": f"{item.trial_days} дн" if item.trial_days else "—",
            "target": item.target_type.upper() if item.target_type else "—",
            "actions": _link(f"/admin/products/{item.id}", "Открыть"),
        })
    return json.dumps(data, default=str)


def serialize_subscriptions(subscriptions: list, request_url_for=None) -> str:
    """Serialize subscriptions for admin grid."""
    data = []
    for item in subscriptions:
        status_class = "ok" if item.status == "active" else "warn" if item.status == "trial" else "danger"

        period_text = ""
        if item.period_start and item.period_end:
            period_text = f"{_fmt_dt(item.period_start)} – {_fmt_dt(item.period_end)}"

        data.append({
            "client": f"<strong>{item.subscriber.display_name}</strong><br>{item.subscriber.email}",
            "product": item.product.title if item.product else "—",
            "status": _badge(item.status.upper(), status_class),
            "period": period_text,
            "target": "—",
            "source": item.source if item.source else "—",
            "actions": _link(f"/admin/subscriptions/{item.id}", "Подробнее"),
        })
    return json.dumps(data, default=str)


def serialize_payments(payments: list, request_url_for=None) -> str:
    """Serialize payments for admin grid."""
    data = []
    for item in payments:
        status_class = "ok" if item.status == "confirmed" else "warn" if item.status == "pending" else "danger"

        data.append({
            "client": f"<strong>{item.subscriber.display_name}</strong><br>{item.subscriber.email}",
            "product": item.product.title if item.product else "—",
            "status": _badge(item.status.upper(), status_class),
            "provider": item.provider.upper() if item.provider else "—",
            "amount": f"{item.amount_rub:,.0f} ₽" if item.amount_rub else "—",
            "subs_count": str(item.subscription_count) if item.subscription_count else "—",
            "actions": _link(f"/admin/payments/{item.id}", "Подробнее"),
        })
    return json.dumps(data, default=str)


def serialize_legal(documents: list, request_url_for=None) -> str:
    """Serialize legal documents for admin grid."""
    data = []
    for item in documents:
        status_class = "ok" if item.status == "active" else "warn"

        data.append({
            "title": f"<strong>{item.title}</strong><br>{_fmt_dt(item.published_at)}",
            "type": item.kind.upper() if item.kind else "—",
            "version": str(item.version) if item.version else "1",
            "status": _badge(item.status.upper(), status_class),
            "consents": str(item.consent_count) if hasattr(item, 'consent_count') else "—",
            "source": _link(f"/docs/{item.slug}", "Просмотр"),
            "actions": _link(f"/admin/legal/{item.id}", "Редактировать"),
        })
    return json.dumps(data, default=str)


def serialize_promos(promo_codes: list, request_url_for=None) -> str:
    """Serialize promo codes for admin grid."""
    data = []
    for item in promo_codes:
        status_class = "ok" if item.status == "active" else "danger"

        data.append({
            "code": f"<strong>{item.code}</strong><br>{item.description[:50]}..." if item.description else "",
            "status": _badge(item.status.upper(), status_class),
            "discount": f"{item.discount_percent}%" if item.discount_percent else f"{item.discount_rub} ₽",
            "used": str(item.uses_count) if item.uses_count else "0",
            "limit": str(item.max_uses) if item.max_uses else "∞",
            "expires": _fmt_dt(item.expires_at) if item.expires_at else "—",
            "actions": _link(f"/admin/promos/{item.id}", "Редактировать"),
        })
    return json.dumps(data, default=str)


def serialize_delivery(records: list, request_url_for=None) -> str:
    """Serialize delivery records for admin grid."""
    data = []
    for item in records:
        status_class = "ok" if item.status == "delivered" else "warn" if item.status == "pending" else "danger"

        data.append({
            "publication": f"<strong>{item.recommendation.title if item.recommendation else '—'}</strong>",
            "strategy": f"{item.recommendation.strategy.title if item.recommendation and item.recommendation.strategy else '—'}",
            "status": _badge(item.status.upper(), status_class),
            "attempts": str(item.attempt_count) if item.attempt_count else "0",
            "delivered": _fmt_dt(item.delivered_at) if item.delivered_at else "—",
            "last_event": item.last_error if item.last_error else "—",
            "actions": _link(f"/admin/delivery/{item.id}", "Подробнее"),
        })
    return json.dumps(data, default=str)


def serialize_lead_analytics(rows: list, request_url_for=None) -> str:
    """Serialize lead analytics for admin grid."""
    data = []
    for row in rows:
        data.append({
            "source": row.get("source", ""),
            "type": row.get("type", ""),
            "users": str(row.get("users", 0)),
            "subs": str(row.get("subs", 0)),
            "active": str(row.get("active", 0)),
            "paid": str(row.get("paid", 0)),
            "revenue": f"{row.get('revenue', 0):,.0f} ₽",
        })
    return json.dumps(data, default=str)


def serialize_metrics_strategies(stats: list, request_url_for=None) -> str:
    """Serialize strategy metrics for admin grid."""
    data = []
    for item in stats:
        data.append({
            "title": item.get("title", "") or "—",
            "sub_count": str(item.get("sub_count", 0)),
        })
    return json.dumps(data, default=str)


def serialize_recommendations(recommendations: list, request_url_for=None) -> str:
    """Serialize recommendations for author grid."""
    data = []
    for item in recommendations:
        side_class = "ok" if item.side and "BUY" in item.side.upper() else "danger"
        status_class = "ok" if item.status == "published" else "warn"

        # Get first leg info if exists
        instrument_text = "—"
        side_text = "—"
        entry_text = "—"
        tp_text = "—"
        stop_text = "—"

        if item.legs and len(item.legs) > 0:
            leg = item.legs[0]
            if leg.instrument:
                instrument_text = leg.instrument.ticker
            side_text = leg.side.upper() if leg.side else "—"
            if leg.entry_from:
                entry_text = f"{leg.entry_from:.2f}"
            if leg.take_profit_1:
                tp_text = f"{leg.take_profit_1:.2f}"
            if leg.stop_loss:
                stop_text = f"{leg.stop_loss:.2f}"

        data.append({
            "strategy": item.strategy.title if item.strategy else "—",
            "idea": f"<strong>{item.title or 'Без названия'}</strong><br>{instrument_text}",
            "side": _badge(side_text, side_class),
            "entry": entry_text,
            "tp1": tp_text,
            "stop": stop_text,
            "status": _badge(item.status.upper(), status_class),
            "updated": _fmt_dt(item.updated_at),
            "actions": _link(f"/author/recommendations/{item.id}", "Открыть"),
        })
    return json.dumps(data, default=str)


def serialize_author_strategies(strategies: list, request_url_for=None) -> str:
    """Serialize author strategies for author grid."""
    data = []
    for item in strategies:
        risk_class = "ok" if item.risk == "low" else "warn" if item.risk == "medium" else "danger"
        status_class = "ok" if item.status == "active" else "warn"

        data.append({
            "title": f"<strong>{item.title}</strong><br>{item.slug}",
            "description": (item.short_description or "")[:60] + "..." if item.short_description and len(item.short_description) > 60 else item.short_description or "",
            "risk": _badge(item.risk.upper(), risk_class),
            "status": _badge(item.status.upper(), status_class),
            "min_capital": f"{item.min_capital:,.0f}" if item.min_capital else "—",
            "actions": _link(f"/author/strategies/{item.id}", "Редактировать"),
        })
    return json.dumps(data, default=str)


def serialize_moderation_queue(items: list, request_url_for=None) -> str:
    """Serialize moderation queue for moderation page grid."""
    data = []
    for item in items:
        kind_class = "warn"
        status_class = "warn" if item.status == "pending" else "ok"

        data.append({
            "publication": f"<strong>{item.recommendation.title if item.recommendation else 'Publication'}</strong>",
            "author": item.recommendation.strategy.author.display_name if item.recommendation and item.recommendation.strategy else "—",
            "strategy": item.recommendation.strategy.title if item.recommendation and item.recommendation.strategy else "—",
            "kind": _badge(item.kind.upper() if item.kind else "REVIEW", kind_class),
            "status": _badge(item.status.upper(), status_class),
            "actions": _link(f"/moderation/{item.id}", "Редактировать"),
        })
    return json.dumps(data, default=str)
