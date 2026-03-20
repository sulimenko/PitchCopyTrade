from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.methods import GetMe
import pytest

from pitchcopytrade.core.config import reset_settings_cache
from pitchcopytrade.bot.dispatcher import build_dispatcher
from pitchcopytrade.bot.handlers.start import HELP_HANDLER, START_HANDLER, _main_keyboard, handle_help, handle_start
from pitchcopytrade.bot.main import (
    _is_retryable_bot_transport_error,
    create_bot,
    run_bot_smoke_check,
    run_polling_with_backoff,
)


@pytest.mark.asyncio
async def test_start_handler_sends_message() -> None:
    message = AsyncMock()
    message.from_user = None
    await handle_start(message)
    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_help_handler_sends_message() -> None:
    message = AsyncMock()
    await handle_help(message)
    message.answer.assert_awaited_once()


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
    assert "Открыть приложение" in labels


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
