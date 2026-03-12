from __future__ import annotations

from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest

from pitchcopytrade.core.config import reset_settings_cache
from pitchcopytrade.bot.dispatcher import build_dispatcher
from pitchcopytrade.bot.handlers.start import HELP_HANDLER, START_HANDLER, _main_keyboard, handle_help, handle_start
from pitchcopytrade.bot.main import create_bot


@pytest.mark.asyncio
async def test_start_handler_replies_with_miniapp_first_message(monkeypatch) -> None:
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
    assert "Mini App внутри Telegram" in sent_text
    assert "/start" in sent_text
    assert "/help" in sent_text
    assert message.answer.await_args.kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_help_handler_replies_with_telegram_usage_guide(monkeypatch) -> None:
    message = AsyncMock()
    await handle_help(message)

    sent_text = message.answer.await_args.args[0]
    assert "Mini App" in sent_text
    assert "Telegram ID" in sent_text
    assert "/help" in sent_text


def test_main_keyboard_hides_webapp_button_for_http_base_url(monkeypatch) -> None:
    reset_settings_cache()
    monkeypatch.setenv("BASE_URL", "http://pct.test.ptfin.ru")

    markup = _main_keyboard()

    labels = [button.text for row in markup.keyboard for button in row]
    assert "Mini App" not in labels
    assert "/help" in labels


def test_main_keyboard_shows_webapp_button_for_https(monkeypatch) -> None:
    reset_settings_cache()
    monkeypatch.setenv("BASE_URL", "https://pct.test.ptfin.ru")

    markup = _main_keyboard()

    labels = [button.text for row in markup.keyboard for button in row]
    assert "Открыть Mini App" in labels
    assert "/help" in labels


def test_build_dispatcher_registers_start_handler() -> None:
    dispatcher = build_dispatcher()
    registered_handlers = dispatcher.message.handlers

    assert len(registered_handlers) == 2
    assert registered_handlers[0].callback is START_HANDLER[0]
    assert registered_handlers[1].callback is HELP_HANDLER[0]
    assert len(dispatcher.callback_query.handlers) == 0


def test_create_bot_uses_provided_token() -> None:
    bot = create_bot("123456:sample-token")

    assert bot.token == "123456:sample-token"
