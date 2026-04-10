from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pitchcopytrade.db.models.catalog import Strategy
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.enums import RiskLevel, StrategyStatus
from pitchcopytrade.services.message_rendering import render_message_email_text, render_message_notification_text


def _make_strategy(title: str = "Top Gun") -> Strategy:
    return Strategy(
        id="strategy-1",
        author_id="author-1",
        slug="top-gun",
        title=title,
        short_description="desc",
        full_description="full",
        risk_level=RiskLevel.MEDIUM,
        status=StrategyStatus.PUBLISHED,
        min_capital_rub=150000,
        is_public=True,
    )


def _make_message(**overrides) -> Message:
    message = Message(
        id="msg-1",
        strategy_id="strategy-1",
        author_id="author-1",
        kind="recommendation",
        status="published",
        type="mixed",
        title="Риск на пробое",
        text={"body": "Ожидаем пробой уровня 255 на повышенных\nобъёмах. Цель — движение к 280 за 2-3 дня."},
        documents=[
            {
                "id": "doc-1",
                "name": "Обзор рынка.pdf",
                "url": "https://example.com/docs/1",
            },
            {
                "id": "doc-2",
                "name": "График.png",
                "url": "https://example.com/docs/2",
            },
        ],
        deals=[
            {
                "ticker": "SBER",
                "side": "buy",
                "price": "250",
                "take_profit_1": "280",
                "stop_loss": "240",
                "quantity": "100",
                "note": "Следить за объёмом входа.",
            }
        ],
        published=datetime(2026, 3, 12, tzinfo=timezone.utc),
    )
    message.strategy = _make_strategy()
    for key, value in overrides.items():
        setattr(message, key, value)
    return message


def test_render_message_notification_text_strict_html_format() -> None:
    message = _make_message()

    text = render_message_notification_text(message)

    assert text.startswith("◼ <b>Риск на пробое</b> · <i>Top Gun</i>")
    assert "Новая публикация по вашей подписке" not in text
    assert "Тип: recommendation" not in text
    assert "Описание" not in text
    assert "Structured сделка" not in text
    assert "✅" not in text
    assert "🟢 Купить" in text
    assert "<b>Вход:</b> 250" in text
    assert "<b>Цель:</b> 280" in text
    assert "<b>Стоп:</b> 240" in text
    assert "📎 <a href=\"https://example.com/docs/1\">Обзор рынка.pdf</a>  📎 <a href=\"https://example.com/docs/2\">График.png</a>" in text
    assert text.index("Ожидаем пробой уровня 255") < text.index("━━━━━━━━━━━━━━━━━━━━") < text.index("<b>SBER</b>  🟢 Купить")
    assert text.rfind("━━━━━━━━━━━━━━━━━━━━") < text.index("<i>Top Gun • PitchCopyTrade</i>")


@pytest.mark.parametrize(
    ("kind", "expected_icon"),
    [
        ("recommendation", "◼"),
        ("idea", "◻"),
        ("alert", "▲"),
        ("unknown", "◼"),
    ],
)
def test_render_message_notification_text_uses_kind_icons(kind: str, expected_icon: str) -> None:
    message = _make_message(kind=kind, deals=[], documents=[], text={"body": "", "plain": ""})

    text = render_message_notification_text(message)

    assert text.startswith(f"{expected_icon} <b>Риск на пробое</b> · <i>Top Gun</i>")
    assert "Тип:" not in text


def test_render_message_notification_text_escapes_body_and_omits_empty_sections() -> None:
    message = _make_message(
        text={"body": "<script>alert(1)</script>", "plain": "<script>alert(1)</script>"},
        deals=[],
        documents=[],
    )

    text = render_message_notification_text(message)

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text
    assert "Описание" not in text
    assert "Structured сделка" not in text
    assert "Документы" not in text
    assert text.count("━━━━━━━━━━━━━━━━━━━━") == 1
    assert text.endswith("<i>Top Gun • PitchCopyTrade</i>")


def test_render_message_notification_text_preserves_newlines_without_br() -> None:
    message = _make_message(
        title="Риск\nна пробое",
        text={"body": "Первая строка\nВторая строка", "plain": "Первая строка\r\nВторая строка"},
        deals=[
            {
                "ticker": "SBER",
                "side": "buy",
                "price": "250\n252",
                "take_profit_1": "280",
                "stop_loss": "240",
                "quantity": "100",
                "note": "Проверить\nобъем",
            }
        ],
    )

    text = render_message_notification_text(message)

    assert "<br>" not in text
    assert "Риск\nна пробое" in text
    assert "Первая строка\nВторая строка" in text
    assert "<b>Вход:</b> 250\n252" in text
    assert "Проверить\nобъем" in text
    assert "&lt;" not in text


def test_render_message_email_text_keeps_flat_format() -> None:
    message = _make_message()

    text = render_message_email_text(message)

    assert "Новая публикация по вашей подписке" in text
    assert "Риск на пробое" in text
    assert "Стратегия: Top Gun" in text
    assert "Тип: recommendation" in text
    assert "Описание" in text
    assert "Structured сделка" in text
    assert "Документы" in text
    assert "• Обзор рынка.pdf" in text
    assert "📎" not in text
