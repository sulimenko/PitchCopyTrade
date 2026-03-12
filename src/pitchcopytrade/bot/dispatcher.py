from __future__ import annotations

from aiogram import Dispatcher

from pitchcopytrade.bot.handlers.feed import (
    FEED_HANDLER,
    PAYMENTS_HANDLER,
    STATUS_HANDLER,
    SUBSCRIPTIONS_HANDLER,
    VERIFY_HANDLER,
    WEB_HANDLER,
)
from pitchcopytrade.bot.handlers.shop import BUY_CONFIRM_HANDLER, BUY_PREVIEW_HANDLER, CATALOG_HANDLER, SHOP_CALLBACK_HANDLER
from pitchcopytrade.bot.handlers.start import START_HANDLER


def build_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    for handler, command in (
        START_HANDLER,
        CATALOG_HANDLER,
        BUY_PREVIEW_HANDLER,
        BUY_CONFIRM_HANDLER,
        FEED_HANDLER,
        STATUS_HANDLER,
        SUBSCRIPTIONS_HANDLER,
        PAYMENTS_HANDLER,
        WEB_HANDLER,
        VERIFY_HANDLER,
    ):
        dispatcher.message.register(handler, command)
    dispatcher.callback_query.register(SHOP_CALLBACK_HANDLER)
    return dispatcher
