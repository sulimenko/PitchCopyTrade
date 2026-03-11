from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pitchcopytrade.bot.dispatcher import build_dispatcher
from pitchcopytrade.bot.handlers.feed import FEED_HANDLER, WEB_HANDLER
from pitchcopytrade.bot.handlers.shop import BUY_CONFIRM_HANDLER, BUY_PREVIEW_HANDLER, CATALOG_HANDLER
from pitchcopytrade.bot.handlers.start import START_HANDLER, handle_start
from pitchcopytrade.bot.main import create_bot


@pytest.mark.asyncio
async def test_start_handler_replies_with_telegram_first_placeholder(monkeypatch) -> None:
    message = AsyncMock()
    message.from_user = None

    class DummySessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("pitchcopytrade.bot.handlers.start.AsyncSessionLocal", lambda: DummySessionContext())

    await handle_start(message)

    message.answer.assert_awaited_once()
    sent_text = message.answer.await_args.args[0]
    assert "PitchCopyTrade запущен." in sent_text
    assert "/catalog" in sent_text
    assert "/confirm_buy" in sent_text


def test_build_dispatcher_registers_start_handler() -> None:
    dispatcher = build_dispatcher()
    registered_handlers = dispatcher.message.handlers

    assert len(registered_handlers) == 6
    assert registered_handlers[0].callback is START_HANDLER[0]
    assert registered_handlers[1].callback is CATALOG_HANDLER[0]
    assert registered_handlers[2].callback is BUY_PREVIEW_HANDLER[0]
    assert registered_handlers[3].callback is BUY_CONFIRM_HANDLER[0]
    assert registered_handlers[4].callback is FEED_HANDLER[0]
    assert registered_handlers[5].callback is WEB_HANDLER[0]


def test_create_bot_uses_provided_token() -> None:
    bot = create_bot("123456:sample-token")

    assert bot.token == "123456:sample-token"
