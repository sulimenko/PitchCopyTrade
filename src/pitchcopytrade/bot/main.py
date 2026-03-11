from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from pitchcopytrade.bot.handlers.start import START_HANDLER
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.core.logging import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

async def run_bot() -> None:
    settings = get_settings()

    if settings.telegram_bot_token.startswith("__FILL_ME__"):
        logger.warning("Telegram token is a placeholder. Bot process is idling.")
        while True:
            await asyncio.sleep(3600)

    dp = Dispatcher()
    handler, command = START_HANDLER
    dp.message.register(handler, command)

    bot = Bot(token=settings.telegram_bot_token)
    logger.info("Starting bot polling")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run_bot())
