from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pitchcopytrade.bot.dispatcher import build_dispatcher
from pitchcopytrade.bot.handlers.start import START_HANDLER, handle_start
from pitchcopytrade.bot.main import create_bot


@pytest.mark.asyncio
async def test_start_handler_replies_with_foundation_placeholder() -> None:
    message = AsyncMock()

    await handle_start(message)

    message.answer.assert_awaited_once()
    sent_text = message.answer.await_args.args[0]
    assert "PitchCopyTrade foundation запущен." in sent_text
    assert "витрина стратегий" in sent_text


def test_build_dispatcher_registers_start_handler() -> None:
    dispatcher = build_dispatcher()
    registered_handlers = dispatcher.message.handlers

    assert len(registered_handlers) == 1
    assert registered_handlers[0].callback is START_HANDLER[0]


def test_create_bot_uses_provided_token() -> None:
    bot = create_bot("123456:sample-token")

    assert bot.token == "123456:sample-token"
