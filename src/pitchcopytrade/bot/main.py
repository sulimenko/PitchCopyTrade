from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from pitchcopytrade.bot.dispatcher import build_dispatcher
from pitchcopytrade.core.runtime import bootstrap_runtime

logger = logging.getLogger(__name__)


def create_bot(token: str) -> Bot:
    return Bot(token=token)

async def run_bot() -> None:
    settings = bootstrap_runtime("bot")

    dp: Dispatcher = build_dispatcher()

    bot = create_bot(settings.telegram.bot_token.get_secret_value())
    logger.info("Starting bot polling")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run_bot())
