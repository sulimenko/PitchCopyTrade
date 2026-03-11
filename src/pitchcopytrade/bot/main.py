from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

from pitchcopytrade.core.config import get_settings
from pitchcopytrade.core.logging import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


async def _handle_start(message: Message) -> None:
    await message.answer(
        "PitchCopyTrade foundation запущен.\n"
        "Дальше будут витрина стратегий, подписки и публикация рекомендаций."
    )


async def run_bot() -> None:
    settings = get_settings()

    if settings.telegram_bot_token.startswith("__FILL_ME__"):
        logger.warning("Telegram token is a placeholder. Bot process is idling.")
        while True:
            await asyncio.sleep(3600)

    dp = Dispatcher()
    dp.message.register(_handle_start, CommandStart())

    bot = Bot(token=settings.telegram_bot_token)
    logger.info("Starting bot polling")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run_bot())
