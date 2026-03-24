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


def _enum_str(val) -> str:
    """Safely convert enum or string to uppercase string."""
    if val is None:
        return ""
    return str(val.value if hasattr(val, 'value') else val).upper()


# P4.4: Russian status labels mapping
_STATUS_LABELS = {
    "ACTIVE": "Активен", "INACTIVE": "Неактивен", "INVITED": "Приглашён",
    "BLOCKED": "Заблокирован", "TRIAL": "Пробный", "EXPIRED": "Истёк",
    "PENDING": "Ожидание", "PAID": "Оплачен", "FAILED": "Ошибка",
    "REFUNDED": "Возврат", "DRAFT": "Черновик", "REVIEW": "На модерации",
    "APPROVED": "Одобрено", "SCHEDULED": "Запланировано",
    "PUBLISHED": "Опубликовано", "CLOSED": "Закрыто",
    "CANCELLED": "Отменено", "ARCHIVED": "Архив",
    "BUY": "Покупка", "SELL": "Продажа",
    "TRUE": "Да", "FALSE": "Нет",
}


def _label(val: str) -> str:
    """Get Russian label for enum value."""
    if val is None:
        return ""
    upper_val = val.upper() if isinstance(val, str) else _enum_str(val)
    return _STATUS_LABELS.get(upper_val, upper_val)


def serialize_strategies(strategies: list, request_url_for=None) -> str:
    """Serialize strategies for admin grid."""
    data = []
    for item in strategies:
        # risk_level is RiskLevel enum
        risk_val = _enum_str(item.risk_level)
        risk_class = "ok" if risk_val == "LOW" else "warn" if risk_val == "MEDIUM" else "danger"
        status_val = _enum_str(item.status)
        status_class = "ok" if status_val == "ACTIVE" else "warn"

        data.append({
            "strategy": f"<strong>{item.title}</strong><br><small>{item.slug}</small>",
            "author": item.author.display_name if item.author else "",
            "risk": _badge(risk_val, risk_class),
            "status": _badge(status_val, status_class),
            "is_public": "Да" if item.is_public else "Нет",
            "min_capital": f"{item.min_capital_rub:,.0f}" if item.min_capital_rub else "—",
            "actions": _link(f"/admin/strategies/{item.id}/edit", "Открыть"),
        })
    return json.dumps(data, default=str)


def serialize_authors(authors: list, request_url_for=None) -> str:
    """Serialize authors for admin grid. Data comes from _author_row() dicts."""
    data = []
    for item in authors:
        # item is a dict from _author_row()
        status = item.get("status", "inactive")
        status_class = "ok" if status == "active" else "warn" if status == "pending" else "danger"
        invite_status = ""
        if item.get("invite_token_version", 0) > 0:
            invite_status = _badge("Отправлено", "ok")
        elif item.get("invite_delivery_status") == "FAILED":
            invite_status = _badge("Ошибка", "danger")

        actions_html = ""
        if item.get("has_linked_user"):
            actions_html = f'<button type="button" class="ghost" data-open-staff-dialog="author-edit-{item.get("id")}">Редактировать</button>'
        else:
            actions_html = '<span class="muted">Недоступно</span>'

        data.append({
            "name": f"<strong>{item.get('display_name', '—')}</strong><br>{item.get('email', '')}",
            "email": item.get("email", ""),
            "telegram_id": str(item.get("telegram_user_id")) if item.get("telegram_user_id") else "—",
            "moderation": f'<form method="post" action="/admin/authors/{item.get("id")}/moderation"><input type="checkbox" {"checked" if item.get("requires_moderation") else ""} onchange="this.form.submit()"></form>',
            "status": _badge(_label(status), status_class),
            "invite": invite_status,
            "actions": actions_html,
        })
    return json.dumps(data, default=str)


def serialize_staff(staff: list, current_user_id: str | None = None, request_url_for=None) -> str:
    """Serialize staff members for admin grid. Data comes from _staff_row() dicts."""
    data = []
    for item in staff:
        # item is a dict from _staff_row()
        roles = item.get("roles", [])
        roles_html = " ".join(_badge(_label(role), "ok") for role in roles)
        status = item.get("status", "active")
        status_class = "ok" if status == "active" else "danger"

        name_suffix = " <small>(это вы)</small>" if item.get("id") == current_user_id else ""
        invite_status = ""
        if item.get("invite_delivery_status") == "SENT":
            invite_status = _badge("Отправлено", "ok")
        elif item.get("invite_delivery_status") == "FAILED":
            invite_status = _badge("Ошибка", "danger")

        # Staff actions dropdown (P4.1: use data-open-staff-dialog instead of href)
        staff_id = item.get('id')
        actions_html = f'''<details class="staff-row-menu">
  <summary class="staff-btn ghost">⋮ Действия</summary>
  <div class="staff-row-menu-panel">
    <button type="button" class="staff-btn ghost" data-open-staff-dialog="staff-edit-{staff_id}">Редактировать</button>
    <button type="button" class="ghost" data-open-staff-dialog="staff-edit-{staff_id}">Диалог</button>
  </div>
</details>'''

        data.append({
            "name": f"<strong>{item.get('display_name', '—')}</strong><br>{item.get('email', '')}{name_suffix}",
            "roles": roles_html,
            "status": _badge(_label(status), status_class),
            "invite": invite_status,
            "telegram_id": str(item.get("telegram_user_id")) if item.get("telegram_user_id") else "—",
            "actions": actions_html,
        })
    return json.dumps(data, default=str)


def serialize_products(products: list, request_url_for=None) -> str:
    """Serialize products for admin grid."""
    data = []
    for item in products:
        is_active = item.is_active if hasattr(item, 'is_active') else True
        status_class = "ok" if is_active else "danger"
        product_type = _enum_str(item.product_type)
        billing_period = _enum_str(item.billing_period)
        period_label = "Месяц" if billing_period == "MONTHLY" else "Квартал" if billing_period == "QUARTERLY" else "Год" if billing_period == "ANNUAL" else "На всегда"

        data.append({
            "product": f"<strong>{item.title}</strong><br>{item.slug}",
            "type": product_type,
            "period": period_label,
            "status": _badge("Активен" if is_active else "Неактивен", status_class),
            "price": f"{item.price_rub:,.0f} ₽" if item.price_rub else "—",
            "trial": f"{item.trial_days} дн" if item.trial_days else "—",
            "target": product_type,
            "actions": _link(f"/admin/products/{item.id}/edit", "Открыть"),
        })
    return json.dumps(data, default=str)


def serialize_subscriptions(subscriptions: list, request_url_for=None) -> str:
    """Serialize subscriptions for admin grid."""
    data = []
    for item in subscriptions:
        status_val = _enum_str(item.status)
        status_class = "ok" if status_val == "ACTIVE" else "warn" if status_val == "TRIAL" else "danger"

        period_text = ""
        if item.start_at and item.end_at:
            period_text = f"{_fmt_dt(item.start_at)} – {_fmt_dt(item.end_at)}"

        user_display = "—"
        if item.user:
            user_display = item.user.full_name or item.user.email or item.user.username or "—"

        lead_source_name = item.lead_source.slug if item.lead_source else "—"

        data.append({
            "client": f"<strong>{user_display}</strong><br>{item.user.email if item.user else ''}",
            "product": item.product.title if item.product else "—",
            "status": _badge(status_val, status_class),
            "period": period_text,
            "target": "—",
            "source": lead_source_name,
            "actions": _link(f"/admin/subscriptions/{item.id}", "Подробнее"),
        })
    return json.dumps(data, default=str)


def serialize_payments(payments: list, request_url_for=None) -> str:
    """Serialize payments for admin grid."""
    data = []
    for item in payments:
        status_val = _enum_str(item.status)
        status_class = "ok" if status_val == "CONFIRMED" else "warn" if status_val == "CREATED" else "danger"
        provider_val = _enum_str(item.provider)

        user_display = "—"
        if item.user:
            user_display = item.user.full_name or item.user.email or item.user.username or "—"

        subs_count = len(item.subscriptions) if item.subscriptions else 0

        data.append({
            "client": f"<strong>{user_display}</strong><br>{item.user.email if item.user else ''}",
            "product": item.product.title if item.product else "—",
            "status": _badge(status_val, status_class),
            "provider": provider_val,
            "amount": f"{item.final_amount_rub:,.0f} ₽" if item.final_amount_rub else "—",
            "subs_count": str(subs_count) if subs_count else "—",
            "actions": _link(f"/admin/payments/{item.id}", "Подробнее"),
        })
    return json.dumps(data, default=str)


def serialize_legal(documents: list, request_url_for=None) -> str:
    """Serialize legal documents for admin grid."""
    data = []
    for item in documents:
        is_active = item.is_active if hasattr(item, 'is_active') else False
        status_class = "ok" if is_active else "warn"
        doc_type = _enum_str(item.document_type)
        consents_count = len(item.consents) if item.consents else 0

        data.append({
            "title": f"<strong>{item.title}</strong><br>{_fmt_dt(item.published_at)}",
            "type": doc_type,
            "version": str(item.version) if item.version else "1",
            "status": _badge("Активен" if is_active else "Черновик", status_class),
            "consents": str(consents_count) if consents_count > 0 else "—",
            "source": _link(f"/admin/legal/{item.id}", "Просмотр"),
            "actions": _link(f"/admin/legal/{item.id}/edit", "Редактировать"),
        })
    return json.dumps(data, default=str)


def serialize_promos(promo_codes: list, request_url_for=None) -> str:
    """Serialize promo codes for admin grid."""
    data = []
    for item in promo_codes:
        is_active = item.is_active if hasattr(item, 'is_active') else True
        status_class = "ok" if is_active else "danger"

        discount_text = ""
        if item.discount_percent:
            discount_text = f"{item.discount_percent}%"
        elif item.discount_amount_rub:
            discount_text = f"{item.discount_amount_rub} ₽"
        else:
            discount_text = "—"

        data.append({
            "code": f"<strong>{item.code}</strong><br>{(item.description or '')[:50]}" + ("..." if item.description and len(item.description) > 50 else ""),
            "status": _badge("Активен" if is_active else "Неактивен", status_class),
            "discount": discount_text,
            "used": str(item.current_redemptions) if item.current_redemptions else "0",
            "limit": str(item.max_redemptions) if item.max_redemptions else "∞",
            "expires": _fmt_dt(item.expires_at) if item.expires_at else "—",
            "actions": _link(f"/admin/promos/{item.id}/edit", "Редактировать"),
        })
    return json.dumps(data, default=str)


def serialize_delivery(records: list, request_url_for=None) -> str:
    """Serialize delivery records for admin grid. Records are DeliveryRecord dataclass."""
    data = []
    for item in records:
        # DeliveryRecord: has recommendation, events, latest_delivery_event, delivery_attempts, delivered_recipients
        rec = item.recommendation
        delivery_status = "delivered" if item.delivered_recipients > 0 else "pending" if item.delivery_attempts == 0 else "failed"
        status_class = "ok" if delivery_status == "delivered" else "warn" if delivery_status == "pending" else "danger"

        latest_event_date = None
        if item.latest_delivery_event:
            latest_event_date = item.latest_delivery_event.created_at

        data.append({
            "publication": f"<strong>{rec.title if rec else '—'}</strong>",
            "strategy": f"{rec.strategy.title if rec and rec.strategy else '—'}",
            "status": _badge(_label(delivery_status), status_class),
            "attempts": str(item.delivery_attempts) if item.delivery_attempts else "0",
            "delivered": _fmt_dt(latest_event_date) if latest_event_date else "—",
            "last_event": item.latest_delivery_event.payload.get("error") if item.latest_delivery_event and item.latest_delivery_event.payload else "—",
            "actions": _link(f"/admin/delivery/{item.recommendation.id}", "Подробнее"),
        })
    return json.dumps(data, default=str)


def serialize_lead_analytics(rows: list, request_url_for=None) -> str:
    """Serialize lead analytics for admin grid. Rows are LeadSourceAnalyticsRow dataclass."""
    data = []
    for row in rows:
        # LeadSourceAnalyticsRow has: source_name, source_type, users_total, subscriptions_total,
        # active_subscriptions, payments_total, paid_payments, revenue_rub
        data.append({
            "source": row.source_name,
            "type": row.source_type,
            "users": str(row.users_total),
            "subs": str(row.subscriptions_total),
            "active": str(row.active_subscriptions),
            "paid": str(row.paid_payments),
            "revenue": f"{row.revenue_rub:,.0f} ₽",
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
    """Serialize recommendations for author grid. P3.2: with inline editing."""
    data = []
    for item in recommendations:
        status_val = _enum_str(item.status)
        status_class = "ok" if status_val == "PUBLISHED" else "warn"

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
            side_val = _enum_str(leg.side)
            # P4.3: Russian side labels
            side_text = "Покупка" if side_val == "BUY" else "Продажа" if side_val == "SELL" else side_val
            side_class = "ok" if side_val == "BUY" else "danger"
            if leg.entry_from:
                entry_text = f"{leg.entry_from:.2f}"
            if leg.take_profit_1:
                tp_text = f"{leg.take_profit_1:.2f}"
            if leg.stop_loss:
                stop_text = f"{leg.stop_loss:.2f}"

        # P3.2: Make fields inline-editable
        title_html = f'<span class="inline-editable" data-rec-id="{item.id}" data-field="title" data-value="{item.title or ""}" contenteditable="false" tabindex="0"><strong>{item.title or "Без названия"}</strong></span><br>{instrument_text}'
        entry_html = f'<span class="inline-editable" data-rec-id="{item.id}" data-field="entry_from" data-value="{entry_text if entry_text != "—" else ""}" contenteditable="false" tabindex="0">{entry_text}</span>'
        tp1_html = f'<span class="inline-editable" data-rec-id="{item.id}" data-field="take_profit_1" data-value="{tp_text if tp_text != "—" else ""}" contenteditable="false" tabindex="0">{tp_text}</span>'
        stop_html = f'<span class="inline-editable" data-rec-id="{item.id}" data-field="stop_loss" data-value="{stop_text if stop_text != "—" else ""}" contenteditable="false" tabindex="0">{stop_text}</span>'

        # P3.2: Status as clickable select (P4.3: Russian labels)
        status_select = f'''<select class="inline-status-select" data-rec-id="{item.id}" data-field="status">
  <option value="draft" {"selected" if status_val == "DRAFT" else ""}>Черновик</option>
  <option value="review" {"selected" if status_val == "REVIEW" else ""}>На модерации</option>
  <option value="published" {"selected" if status_val == "PUBLISHED" else ""}>Опубликовано</option>
</select>'''

        data.append({
            "strategy": item.strategy.title if item.strategy else "—",
            "idea": title_html,
            "side": _badge(side_text, side_class if side_text != "—" else ""),
            "entry": entry_html,
            "tp1": tp1_html,
            "stop": stop_html,
            "status": status_select,
            "updated": _fmt_dt(item.updated_at),
            "actions": _link(f"/author/recommendations/{item.id}/edit", "Открыть"),
        })
    return json.dumps(data, default=str)


def serialize_author_strategies(strategies: list, request_url_for=None) -> str:
    """Serialize author strategies for author grid."""
    data = []
    for item in strategies:
        risk_val = _enum_str(item.risk_level)
        risk_class = "ok" if risk_val == "LOW" else "warn" if risk_val == "MEDIUM" else "danger"
        status_val = _enum_str(item.status)
        status_class = "ok" if status_val == "ACTIVE" else "warn"

        data.append({
            "title": f"<strong>{item.title}</strong><br>{item.slug}",
            "description": (item.short_description or "")[:60] + "..." if item.short_description and len(item.short_description) > 60 else item.short_description or "",
            "risk": _badge(risk_val, risk_class),
            "status": _badge(status_val, status_class),
            "min_capital": f"{item.min_capital_rub:,.0f}" if item.min_capital_rub else "—",
            "actions": _link(f"/author/strategies/{item.id}/edit", "Редактировать"),
        })
    return json.dumps(data, default=str)


def serialize_moderation_queue(items: list, request_url_for=None) -> str:
    """Serialize moderation queue for moderation page grid. Items are Recommendation objects."""
    data = []
    for item in items:
        # item is Recommendation object directly
        kind_val = _enum_str(item.kind)
        kind_class = "warn"
        status_val = _enum_str(item.status)
        status_class = "warn" if status_val == "DRAFT" else "ok"

        author_name = "—"
        if item.strategy and item.strategy.author:
            author_name = item.strategy.author.display_name

        data.append({
            "publication": f"<strong>{item.title or 'Publication'}</strong>",
            "author": author_name,
            "strategy": item.strategy.title if item.strategy else "—",
            "kind": _badge(kind_val, kind_class),
            "status": _badge(status_val, status_class),
            "actions": _link(f"/moderation/recommendations/{item.id}", "Редактировать"),
        })
    return json.dumps(data, default=str)
