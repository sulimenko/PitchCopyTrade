from __future__ import annotations

from aiogram import Dispatcher

from pitchcopytrade.bot.handlers.start import START_HANDLER


def build_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    handler, command = START_HANDLER
    dispatcher.message.register(handler, command)
    return dispatcher
