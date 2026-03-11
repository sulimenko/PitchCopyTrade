from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from pitchcopytrade.bot.handlers.start import START_HANDLER
from pitchcopytrade.core.runtime import bootstrap_runtime

logger = logging.getLogger(__name__)

async def run_bot() -> None:
    settings = bootstrap_runtime("bot")

    dp = Dispatcher()
    handler, command = START_HANDLER
    dp.message.register(handler, command)

    bot = Bot(token=settings.telegram.bot_token.get_secret_value())
    logger.info("Starting bot polling")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run_bot())
