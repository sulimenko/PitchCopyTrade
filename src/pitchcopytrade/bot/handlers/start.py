from __future__ import annotations

from aiogram.filters import CommandStart
from aiogram.types import Message


async def handle_start(message: Message) -> None:
    await message.answer(
        "PitchCopyTrade foundation запущен.\n"
        "Дальше будут витрина стратегий, подписки и публикация рекомендаций."
    )


START_HANDLER = (handle_start, CommandStart())
