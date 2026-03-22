from __future__ import annotations

from urllib.parse import quote

from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from pitchcopytrade.auth.session import decode_staff_invite_context
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
    payload = ""
    if message.text and " " in message.text:
        payload = message.text.split(" ", 1)[1].strip()
    if payload.startswith("staffinvite-"):
        try:
            invite_token = decode_staff_invite_context(payload.removeprefix("staffinvite-"))
        except Exception:
            await message.answer("Приглашение не удалось прочитать. Попросите администратора отправить новое.")
            return
        invite_url = f"{get_settings().app.base_url.rstrip('/')}/login?invite_token={quote(invite_token, safe='')}"
        # X3.3: Use WebAppInfo to open invite page inside Telegram WebView
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="Открыть приглашение", web_app=WebAppInfo(url=invite_url)),
            ]]
        )
        await message.answer("Приглашение сотрудника открыто. Откройте через кнопку ниже.", reply_markup=keyboard)
        return
    if payload.startswith("staffinvitehelp-"):
        try:
            invite_token = decode_staff_invite_context(payload.removeprefix("staffinvitehelp-"))
        except Exception:
            await message.answer("Контекст приглашения не удалось прочитать. Попросите администратора отправить новое письмо.")
            return
        invite_url = f"{get_settings().app.base_url.rstrip('/')}/login?invite_token={quote(invite_token, safe='')}"
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="Открыть приглашение снова", url=invite_url),
            ]]
        )
        await message.answer("Если приглашение устарело или не открылось, попросите администратора отправить новое письмо. Текущую ссылку можно открыть кнопкой ниже.", reply_markup=keyboard)
        return
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
