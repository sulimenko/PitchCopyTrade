from __future__ import annotations

import base64
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.methods import GetMe
import pytest

from pitchcopytrade.core.config import reset_settings_cache
from pitchcopytrade.auth.session import build_staff_invite_token, encode_staff_invite_context
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.bot.dispatcher import build_dispatcher
from pitchcopytrade.bot.handlers.start import HELP_HANDLER, START_HANDLER, _main_keyboard, handle_help, handle_start
from pitchcopytrade.bot.main import (
    _is_retryable_bot_transport_error,
    create_bot,
    run_bot,
    run_bot_smoke_check,
    run_polling_with_backoff,
)


@pytest.mark.asyncio
async def test_start_handler_sends_message() -> None:
    message = AsyncMock()
    message.from_user = None
    await handle_start(message)
    message.answer.assert_awaited_once()
    assert "каталог стратегий" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_start_handler_staff_invite_uses_plain_url_button() -> None:
    message = AsyncMock()
    invite_token = "invite-token-123"
    payload = base64.urlsafe_b64encode(invite_token.encode("utf-8")).decode("ascii").rstrip("=")
    message.text = f"/start staffinvite-{payload}"

    await handle_start(message)

    message.answer.assert_awaited_once()
    markup = message.answer.await_args.kwargs["reply_markup"]
    buttons = [button for row in markup.inline_keyboard for button in row]
    assert buttons[0].url is not None
    assert buttons[0].web_app is None
    assert buttons[0].url.endswith("/login?invite_token=invite-token-123")


@pytest.mark.asyncio
async def test_start_handler_staff_invite_help_rejects_invalid_token() -> None:
    message = AsyncMock()
    payload = base64.urlsafe_b64encode(b"invalid-token").decode("ascii").rstrip("=")
    message.text = f"/start staffinvitehelp-{payload}"

    await handle_start(message)

    message.answer.assert_awaited_once()
    assert "устарело" in message.answer.await_args.args[0]
    assert "reply_markup" not in message.answer.await_args.kwargs


@pytest.mark.asyncio
async def test_start_handler_staff_invite_help_accepts_valid_token() -> None:
    message = AsyncMock()
    user = User(id="staff-1", invite_token_version=1)
    invite_token = build_staff_invite_token(user)
    payload = encode_staff_invite_context(invite_token)
    message.text = f"/start staffinvitehelp-{payload}"

    await handle_start(message)

    message.answer.assert_awaited_once()
    markup = message.answer.await_args.kwargs["reply_markup"]
    buttons = [button for row in markup.inline_keyboard for button in row]
    assert buttons[0].url is not None
    assert buttons[0].text == "Открыть приглашение"


@pytest.mark.asyncio
async def test_help_handler_sends_message() -> None:
    message = AsyncMock()
    await handle_help(message)
    message.answer.assert_awaited_once()
    assert "справк" in message.answer.await_args.args[0]


def test_main_keyboard_returns_none_for_http_base_url(monkeypatch) -> None:
    reset_settings_cache()
    monkeypatch.setenv("BASE_URL", "http://pct.test.ptfin.ru")

    markup = _main_keyboard()
    assert markup is None


def test_main_keyboard_returns_keyboard_for_https(monkeypatch) -> None:
    reset_settings_cache()
    monkeypatch.setenv("BASE_URL", "https://pct.test.ptfin.ru")

    markup = _main_keyboard()
    assert markup is not None
    labels = [button.text for row in markup.inline_keyboard for button in row]
    urls = [button.web_app.url for row in markup.inline_keyboard for button in row if button.web_app is not None]
    assert "Открыть каталог" in labels
    assert any(url.endswith("/app/catalog?entry=bot_start") for url in urls)


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


@pytest.mark.asyncio
async def test_run_polling_with_backoff_retries_transport_failures() -> None:
    dp = AsyncMock()
    bot = AsyncMock()
    bot.get_me = AsyncMock(
        side_effect=[
            TelegramNetworkError(GetMe(), "temporary dns failure"),
            SimpleNamespace(id=1, username="pct_test_bot"),
        ]
    )
    sleep_calls: list[int] = []

    async def fake_sleep(seconds: int) -> None:
        sleep_calls.append(seconds)

    await run_polling_with_backoff(dp, bot, sleep_func=fake_sleep)

    assert sleep_calls == [2]
    dp.start_polling.assert_awaited_once_with(bot, close_bot_session=False)


@pytest.mark.asyncio
async def test_run_polling_with_backoff_raises_fatal_errors_without_retry() -> None:
    dp = AsyncMock()
    bot = AsyncMock()
    bot.get_me = AsyncMock(side_effect=TelegramUnauthorizedError(GetMe(), "invalid token"))
    sleep = AsyncMock()

    with pytest.raises(TelegramUnauthorizedError):
        await run_polling_with_backoff(dp, bot, sleep_func=sleep)

    sleep.assert_not_awaited()
    dp.start_polling.assert_not_called()


@pytest.mark.asyncio
async def test_run_bot_smoke_check_calls_get_me() -> None:
    bot = AsyncMock()
    bot.get_me = AsyncMock(return_value=SimpleNamespace(id=1, username="pct_test_bot"))

    me = await run_bot_smoke_check(bot)

    assert me.username == "pct_test_bot"
    bot.get_me.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_bot_logs_startup_fingerprint(monkeypatch, caplog: pytest.LogCaptureFixture) -> None:
    fake_settings = SimpleNamespace(
        app=SimpleNamespace(base_url="https://pct.test.ptfin.ru"),
        telegram=SimpleNamespace(
            bot_token=SimpleNamespace(get_secret_value=lambda: "123456:valid-token"),
            bot_username="pitchcopytrade_bot",
            use_webhook=False,
        )
    )
    fake_bot = AsyncMock()
    fake_bot.get_me = AsyncMock(return_value=SimpleNamespace(id=1, username="pct_test_bot"))
    fake_bot.set_chat_menu_button = AsyncMock()
    fake_bot.session = type("FakeSession", (), {"close": AsyncMock()})()
    monkeypatch.setattr("pitchcopytrade.bot.main.bootstrap_runtime", lambda service_name: fake_settings)
    monkeypatch.setattr("pitchcopytrade.bot.main.create_bot", lambda token: fake_bot)
    monkeypatch.setattr("pitchcopytrade.bot.main.run_polling_with_backoff", AsyncMock())
    caplog.set_level(logging.INFO)

    await run_bot()

    messages = [record.getMessage() for record in caplog.records]
    assert any("Bot startup complete" in message for message in messages)
    assert any("telegram_bot_username=pitchcopytrade_bot" in message for message in messages)
    assert any("telegram_bot_token_fingerprint=" in message for message in messages)
    assert fake_bot.set_chat_menu_button.await_count == 1
    menu_button = fake_bot.set_chat_menu_button.await_args.kwargs["menu_button"]
    assert menu_button.text == "Открыть каталог"
    assert menu_button.web_app.url.endswith("/app/catalog")
