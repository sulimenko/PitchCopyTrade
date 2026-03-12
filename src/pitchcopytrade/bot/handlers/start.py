from __future__ import annotations

from aiogram.filters import Command, CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, WebAppInfo

from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.session import AsyncSessionLocal
from pitchcopytrade.repositories.public import FilePublicRepository, SqlAlchemyPublicRepository
from pitchcopytrade.services.public import TelegramSubscriberProfile, upsert_telegram_subscriber


def _main_keyboard() -> ReplyKeyboardMarkup:
    base_url = get_settings().app.base_url
    keyboard: list[list[KeyboardButton]] = []
    if base_url.startswith("https://"):
        keyboard.append([KeyboardButton(text="Открыть Mini App", web_app=WebAppInfo(url=f"{base_url}/miniapp"))])
    keyboard.append([KeyboardButton(text="/help")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def _start_text() -> str:
    return (
        "PitchCopyTrade готов к работе.\n"
        "Клиентский путь полностью переведен в Mini App внутри Telegram.\n\n"
        "Что делать дальше:\n"
        "1. Откройте Mini App кнопкой ниже.\n"
        "2. Выберите стратегию в каталоге.\n"
        "3. Оформите подписку и следите за статусом внутри Mini App.\n\n"
        "Доступные команды:\n"
        "/start - открыть стартовое сообщение\n"
        "/help - подсказка по работе сервиса"
    )


def _help_text() -> str:
    lines = [
        "Как пользоваться PitchCopyTrade:",
        "1. Mini App в Telegram — основной интерфейс клиента.",
        "2. В каталоге выберите стратегию и оформите подписку.",
        "3. После оплаты рекомендации и статус доступа доступны внутри Mini App.",
        "4. Команды бота сведены к базовым: /start и /help.",
        "",
        "Важно:",
        "- отдельный клиентский логин не нужен;",
        "- авторизация клиента идет по Telegram ID;",
        "- сайт остается публичной витриной и справочной страницей;",
        "- кабинеты admin и author работают отдельно через web.",
    ]
    if get_settings().app.base_url.startswith("https://"):
        lines.extend(
            [
                "",
                "Если кнопка Mini App не отображается, откройте бот заново и отправьте /start.",
            ]
        )
    return "\n".join(lines)


async def handle_start(message: Message) -> None:
    telegram_user = message.from_user
    if telegram_user is not None:
        profile = TelegramSubscriberProfile(
            telegram_user_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
        )
        if AsyncSessionLocal is None:
            repository = FilePublicRepository()
            user = await upsert_telegram_subscriber(repository, profile)
            await repository.commit()
        else:
            async with AsyncSessionLocal() as session:
                repository = SqlAlchemyPublicRepository(session)
                await upsert_telegram_subscriber(repository, profile)
                await repository.commit()

    await message.answer(_start_text(), reply_markup=_main_keyboard())


async def handle_help(message: Message) -> None:
    await message.answer(_help_text(), reply_markup=_main_keyboard())


START_HANDLER = (handle_start, CommandStart())
HELP_HANDLER = (handle_help, Command("help"))
