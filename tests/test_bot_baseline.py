from __future__ import annotations

from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest

from pitchcopytrade.core.config import reset_settings_cache
from pitchcopytrade.bot.dispatcher import build_dispatcher
from pitchcopytrade.bot.handlers.feed import FEED_HANDLER, PAYMENTS_HANDLER, STATUS_HANDLER, SUBSCRIPTIONS_HANDLER, VERIFY_HANDLER, WEB_HANDLER
from pitchcopytrade.bot.handlers.shop import BUY_CONFIRM_HANDLER, BUY_PREVIEW_HANDLER, CATALOG_HANDLER, SHOP_CALLBACK_HANDLER, _catalog_keyboard
from pitchcopytrade.bot.handlers.start import START_HANDLER, _start_keyboard, handle_start
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
    assert "/status" in sent_text
    assert "/subscriptions" in sent_text
    assert "/payments" in sent_text
    assert "/confirm_buy" in sent_text
    assert message.answer.await_args.kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_start_handler_with_web_payload_returns_verification_link(monkeypatch) -> None:
    message = AsyncMock()
    message.from_user = SimpleNamespace(id=12345, username="leaduser", first_name="Lead", last_name="User")
    user = SimpleNamespace(id="user-1", username="leaduser")

    class DummyRepository:
        async def commit(self) -> None:
            return None

    monkeypatch.setattr("pitchcopytrade.bot.handlers.start.AsyncSessionLocal", None)
    monkeypatch.setattr("pitchcopytrade.bot.handlers.start.FilePublicRepository", lambda: DummyRepository())
    monkeypatch.setattr("pitchcopytrade.bot.handlers.start.upsert_telegram_subscriber", AsyncMock(return_value=user))
    monkeypatch.setattr(
        "pitchcopytrade.bot.handlers.start.build_subscriber_web_message",
        lambda _user, base_url, include_webapp: f"{base_url}/tg-auth?token=sample",
    )

    await handle_start(message, SimpleNamespace(args="web"))

    sent_text = message.answer.await_args.args[0]
    assert "/tg-auth?token=sample" in sent_text


def test_start_keyboard_hides_webapp_button_for_http_base_url(monkeypatch) -> None:
    reset_settings_cache()
    monkeypatch.setenv("BASE_URL", "http://pct.test.ptfin.ru")

    markup = _start_keyboard()

    labels = [button.text for row in markup.keyboard for button in row]
    assert "Mini App" not in labels
    assert "/status" in labels


def test_catalog_keyboard_hides_webapp_button_for_http_base_url(monkeypatch) -> None:
    reset_settings_cache()
    monkeypatch.setenv("BASE_URL", "http://pct.test.ptfin.ru")

    markup = _catalog_keyboard()

    labels = [button.text for row in markup.keyboard for button in row]
    assert "Mini App" not in labels
    assert "/status" in labels


def test_build_dispatcher_registers_start_handler() -> None:
    dispatcher = build_dispatcher()
    registered_handlers = dispatcher.message.handlers

    assert len(registered_handlers) == 10
    assert registered_handlers[0].callback is START_HANDLER[0]
    assert registered_handlers[1].callback is CATALOG_HANDLER[0]
    assert registered_handlers[2].callback is BUY_PREVIEW_HANDLER[0]
    assert registered_handlers[3].callback is BUY_CONFIRM_HANDLER[0]
    assert registered_handlers[4].callback is FEED_HANDLER[0]
    assert registered_handlers[5].callback is STATUS_HANDLER[0]
    assert registered_handlers[6].callback is SUBSCRIPTIONS_HANDLER[0]
    assert registered_handlers[7].callback is PAYMENTS_HANDLER[0]
    assert registered_handlers[8].callback is WEB_HANDLER[0]
    assert registered_handlers[9].callback is VERIFY_HANDLER[0]
    assert len(dispatcher.callback_query.handlers) == 1
    assert dispatcher.callback_query.handlers[0].callback is SHOP_CALLBACK_HANDLER


def test_create_bot_uses_provided_token() -> None:
    bot = create_bot("123456:sample-token")

    assert bot.token == "123456:sample-token"
