from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Instrument, Strategy
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.enums import InstrumentType, RiskLevel, StrategyStatus
from pitchcopytrade.services.notifications import _send_with_retry, build_message_notification_text


def test_build_message_notification_text_uses_html_safe_message_payload() -> None:
    author_user = User(id="author-user-1", full_name="Alpha Desk")
    author = AuthorProfile(id="author-1", user_id="author-user-1", display_name="Alpha Desk", slug="alpha-desk", is_active=True)
    author.user = author_user
    strategy = Strategy(
        id="strategy-1",
        author_id="author-1",
        slug="momentum-ru",
        title="Momentum RU",
        short_description="desc",
        full_description="full",
        risk_level=RiskLevel.MEDIUM,
        status=StrategyStatus.PUBLISHED,
        min_capital_rub=150000,
        is_public=True,
    )
    strategy.author = author
    message = Message(
        id="msg-1",
        strategy_id="strategy-1",
        author_id="author-1",
        kind="idea",
        status="published",
        type="mixed",
        title="Покупка SBER",
        text={"body": "<p>Сильный спрос</p>", "plain": "Сильный спрос"},
        documents=[
            {
                "id": "doc-1",
                "object_key": "messages/msg-1/file.pdf",
                "original_filename": "idea.pdf",
                "content_type": "application/pdf",
                "size_bytes": 123,
            }
        ],
        deals=[
            {
                "instrument_id": "SBER",
                "side": "buy",
                "entry_from": "101.5",
            }
        ],
        published=datetime(2026, 3, 12, tzinfo=timezone.utc),
    )
    message.strategy = strategy

    text = build_message_notification_text(message)

    assert "<b>Новая публикация по вашей подписке</b>" in text
    assert "<b>Покупка SBER</b>" in text
    assert "Стратегия: Momentum RU" in text
    assert "Тип: idea" in text
    assert "<p>Сильный спрос</p>" in text
    assert "Документов: 1" in text
    assert "SBER buy 101.5" in text


@pytest.mark.asyncio
async def test_send_with_retry_recovers_after_first_failure() -> None:
    send_message = AsyncMock(side_effect=[RuntimeError("temp"), None])

    delivered = await _send_with_retry(send_message, 12345, "hello", attempts=3)

    assert delivered is True
    assert send_message.await_count == 2
