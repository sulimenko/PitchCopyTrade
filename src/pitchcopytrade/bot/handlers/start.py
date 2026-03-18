from __future__ import annotations

from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from pitchcopytrade.core.config import get_settings


def _main_keyboard() -> InlineKeyboardMarkup | None:
    base_url = get_settings().app.base_url
    if not base_url.startswith("https://"):
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="Открыть приложение",
                web_app=WebAppInfo(url=f"{base_url}/app/"),
            )
        ]]
    )


async def handle_start(message: Message) -> None:
    keyboard = _main_keyboard()
    if keyboard:
        await message.answer("PitchCopyTrade", reply_markup=keyboard)
    else:
        await message.answer("PitchCopyTrade")


async def handle_help(message: Message) -> None:
    keyboard = _main_keyboard()
    if keyboard:
        await message.answer("PitchCopyTrade", reply_markup=keyboard)
    else:
        await message.answer("PitchCopyTrade")


START_HANDLER = (handle_start, CommandStart())
HELP_HANDLER = (handle_help, Command("help"))
