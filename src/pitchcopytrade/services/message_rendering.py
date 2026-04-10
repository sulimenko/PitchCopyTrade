from __future__ import annotations

from html import escape

from pitchcopytrade.db.models.content import Message


MESSAGE_RENDER_CONTRACT = {
    "block_order": ["text", "structured", "documents"],
    "block_titles": {
        "text": "Описание",
        "structured": "Structured сделка",
        "documents": "Документы",
    },
    "structured_fields": [
        ["instrument", "Инструмент"],
        ["side", "Действие"],
        ["price", "Цена"],
        ["quantity", "Количество"],
        ["amount", "Сумма"],
        ["take_profit", "TP"],
        ["stop_loss", "SL"],
        ["note", "Примечание"],
    ],
}


def build_message_render_contract() -> dict[str, object]:
    return {
        "block_order": list(MESSAGE_RENDER_CONTRACT["block_order"]),
        "block_titles": dict(MESSAGE_RENDER_CONTRACT["block_titles"]),
        "structured_fields": [list(item) for item in MESSAGE_RENDER_CONTRACT["structured_fields"]],
    }


def render_message_notification_text(message: Message) -> str:
    return _render_telegram_content(message)


def render_message_email_text(message: Message) -> str:
    return _render_email_content(message)


_DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
_KIND_ICONS = {
    "recommendation": "◼",
    "idea": "◻",
    "alert": "▲",
}
_SIDE_ICONS = {
    "buy": "🟢",
    "sell": "🔴",
}


def _render_telegram_content(message: Message) -> str:
    kind_icon = _KIND_ICONS.get(str(message.kind or "").strip().lower(), "◼")
    title = _message_title(message)
    strategy_name = _message_strategy_name(message) or "—"

    lines: list[str] = [f"{kind_icon} <b>{_escape_preserving_linebreaks(title)}</b> · <i>{_escape_preserving_linebreaks(strategy_name)}</i>"]

    body = _message_body(message)
    if body:
        lines.extend(["", _escape_preserving_linebreaks(body)])

    deal = _render_telegram_deal(message)
    if deal:
        lines.extend([_DIVIDER, deal])

    documents = _render_telegram_documents(message)
    if documents:
        lines.extend([_DIVIDER, documents])

    footer_name = _message_strategy_name(message)
    if footer_name:
        lines.extend([_DIVIDER, f"<i>{_escape_preserving_linebreaks(footer_name)} • PitchCopyTrade</i>"])
    else:
        lines.extend([_DIVIDER, "<i>PitchCopyTrade</i>"])
    return "\n".join(lines)


def _render_telegram_deal(message: Message) -> str:
    if not message.deals:
        return ""
    deal = message.deals[0] or {}
    lines: list[str] = []
    lines.append(f"<b>{_escape_preserving_linebreaks(_deal_instrument_label(deal))}</b>  {_deal_side_with_icon(deal)}")

    price_parts: list[str] = []
    entry = _deal_value(deal, "price", "entry_from")
    if entry:
        price_parts.append(f"<b>Вход:</b> {_escape_preserving_linebreaks(entry)}")
    tp = _deal_take_profit_label(deal)
    if tp:
        price_parts.append(f"<b>Цель:</b> {_escape_preserving_linebreaks(tp)}")
    sl = _deal_value(deal, "stop_loss", "stop")
    if sl:
        price_parts.append(f"<b>Стоп:</b> {_escape_preserving_linebreaks(sl)}")
    if price_parts:
        lines.append("  ".join(price_parts))

    extra_parts: list[str] = []
    qty = _deal_value(deal, "quantity")
    if qty:
        extra_parts.append(f"<b>Объём:</b> {_escape_preserving_linebreaks(qty)}")
    amount = _deal_value(deal, "amount")
    if amount:
        extra_parts.append(f"<b>Сумма:</b> {_escape_preserving_linebreaks(amount)}")
    if extra_parts:
        lines.append("  ".join(extra_parts))

    note = _deal_value(deal, "note")
    if note:
        lines.extend([_DIVIDER, _escape_preserving_linebreaks(note)])

    return "\n".join(lines)


def _render_telegram_documents(message: Message) -> str:
    documents = [_render_document_link(document) for document in message.documents or []]
    documents = [item for item in documents if item]
    if not documents:
        return ""
    if len(documents) <= 2:
        return "  ".join(f"📎 {item}" for item in documents)
    return "\n".join(f"📎 {item}" for item in documents)


def _render_email_content(message: Message) -> str:
    lines = [
        "Новая публикация по вашей подписке",
        _message_title(message),
        f"Стратегия: {message.strategy.title if message.strategy is not None else 'не указана'}",
        f"Тип: {message.kind}",
    ]

    blocks: list[str] = []
    body = _message_body(message)
    if body:
        blocks.append(_render_text_block(body, escape_markup=False))
    structured = _render_structured_block(message, escape_markup=False)
    if structured:
        blocks.append(structured)
    documents = _render_documents_block(message, escape_markup=False)
    if documents:
        blocks.append(documents)
    return "\n".join(lines + blocks)


def _message_title(message: Message) -> str:
    if message.title:
        return message.title
    if message.strategy is not None and message.strategy.title:
        return message.strategy.title
    return "Публикация"


def _message_body(message: Message) -> str:
    text_payload = message.text or {}
    return str(text_payload.get("body") or text_payload.get("plain") or "").strip()


def _render_text_block(body: str, *, escape_markup: bool) -> str:
    title = "<b>Описание</b>" if escape_markup else "Описание"
    return "\n".join([title, escape(body) if escape_markup else body])


def _render_structured_block(message: Message, *, escape_markup: bool) -> str:
    if not message.deals:
        return ""
    deal = message.deals[0] or {}
    title = "<b>Structured сделка</b>" if escape_markup else "Structured сделка"
    lines = [title]
    field_values = [
        ("instrument", _deal_instrument_label(deal)),
        ("side", _deal_side_label(deal)),
        ("price", _deal_value(deal, "price", "entry_from")),
        ("quantity", _deal_value(deal, "quantity")),
        ("amount", _deal_value(deal, "amount")),
        ("take_profit", _deal_take_profit_label(deal)),
        ("stop_loss", _deal_value(deal, "stop_loss", "stop")),
        ("note", _deal_value(deal, "note")),
    ]
    for key, value in field_values:
        if not value:
            continue
        label = next((item[1] for item in MESSAGE_RENDER_CONTRACT["structured_fields"] if item[0] == key), key)
        if escape_markup:
            lines.append(f"{escape(label)}: {escape(value)}")
        else:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def _render_documents_block(message: Message, *, escape_markup: bool) -> str:
    if not message.documents:
        return ""
    lines = ["<b>Документы</b>" if escape_markup else "Документы"]
    caption = _message_document_caption(message)
    if caption:
        lines.append(escape(caption) if escape_markup else caption)
    for document in message.documents:
        name = _document_name(document)
        if name:
            lines.append(f"• {escape(name)}" if escape_markup else f"• {name}")
    return "\n".join(lines)


def _deal_instrument_label(deal: dict[str, object]) -> str:
    return str(
        deal.get("ticker")
        or deal.get("instrument")
        or deal.get("instrument_id")
        or "инструмент"
    ).strip()


def _deal_side_label(deal: dict[str, object]) -> str:
    side = str(deal.get("side") or "").strip().lower()
    return {"buy": "Купить", "sell": "Продать"}.get(side, side or "n/a")


def _deal_side_with_icon(deal: dict[str, object]) -> str:
    side = str(deal.get("side") or "").strip().lower()
    label = {"buy": "Купить", "sell": "Продать"}.get(side, side or "—")
    icon = _SIDE_ICONS.get(side, "")
    return f"{icon} {label}".strip()


def _deal_value(deal: dict[str, object], *keys: str) -> str:
    for key in keys:
        value = deal.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _deal_take_profit_label(deal: dict[str, object]) -> str:
    value = _deal_value(deal, "take_profit_1")
    if value:
        return value
    targets = deal.get("targets")
    if isinstance(targets, list) and targets:
        first = str(targets[0]).strip()
        if first:
            return first
    return ""


def _message_document_caption(message: Message) -> str:
    text_payload = message.text or {}
    return str(text_payload.get("title") or text_payload.get("caption") or "").strip()


def _document_name(document: object) -> str:
    if isinstance(document, dict):
        for key in ("name", "title", "original_filename", "filename"):
            value = document.get(key)
            if value:
                text = str(value).strip()
                if text:
                    return text
    return ""


def _render_document_link(document: object) -> str:
    if not isinstance(document, dict):
        return ""
    name = _document_name(document)
    if not name:
        return ""
    for key in ("url", "href", "link"):
        value = document.get(key)
        if value:
            href = str(value).strip()
            if href:
                return f'<a href="{escape(href)}">{escape(name)}</a>'
    return escape(name)


def _message_strategy_name(message: Message) -> str:
    if message.strategy is not None and message.strategy.title:
        return str(message.strategy.title).strip()
    return ""


def _escape_preserving_linebreaks(value: str) -> str:
    return escape(value).replace("\r\n", "\n").replace("\r", "\n")
