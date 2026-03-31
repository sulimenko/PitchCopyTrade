from __future__ import annotations

from urllib.parse import quote

from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from pitchcopytrade.auth.session import decode_staff_invite_context
from pitchcopytrade.core.config import get_settings


def _webapp_keyboard(label: str, path: str) -> InlineKeyboardMarkup | None:
    base_url = get_settings().app.base_url
    if not base_url.startswith("https://"):
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text=label,
                web_app=WebAppInfo(url=f"{base_url}{path}"),
            )
        ]]
    )


def _main_keyboard() -> InlineKeyboardMarkup | None:
    return _webapp_keyboard("Открыть каталог", "/app?entry=bot_start")


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
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="Открыть приглашение", url=invite_url),
            ]]
        )
        await message.answer("Приглашение сотрудника открыто. Откройте его по кнопке ниже.", reply_markup=keyboard)
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
        await message.answer("Откройте каталог стратегий в Mini App.", reply_markup=keyboard)
    else:
        await message.answer("Откройте Mini App в браузере по HTTPS, чтобы перейти в каталог стратегий.")


async def handle_help(message: Message) -> None:
    keyboard = _webapp_keyboard("Открыть помощь", "/app/help")
    if keyboard:
        await message.answer("Откройте справку внутри Mini App.", reply_markup=keyboard)
    else:
        await message.answer("Откройте Mini App в браузере по HTTPS, чтобы перейти к справке.")


START_HANDLER = (handle_start, CommandStart())
HELP_HANDLER = (handle_help, Command("help"))
