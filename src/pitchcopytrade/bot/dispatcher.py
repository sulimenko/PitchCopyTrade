from __future__ import annotations

from aiogram import Dispatcher

from pitchcopytrade.bot.handlers.start import HELP_HANDLER, START_HANDLER


def build_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    for handler, command in (START_HANDLER, HELP_HANDLER):
        dispatcher.message.register(handler, command)
    return dispatcher
