from __future__ import annotations

from aiogram.filters import CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, WebAppInfo

from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.session import AsyncSessionLocal
from pitchcopytrade.repositories.public import FilePublicRepository, SqlAlchemyPublicRepository
from pitchcopytrade.services.public import TelegramSubscriberProfile, upsert_telegram_subscriber


def _start_keyboard() -> ReplyKeyboardMarkup:
    base_url = get_settings().app.base_url
    keyboard = [
        [KeyboardButton(text="/catalog"), KeyboardButton(text="/feed")],
        [KeyboardButton(text="/web")],
    ]
    if base_url.startswith("https://"):
        keyboard[1].append(KeyboardButton(text="Mini App", web_app=WebAppInfo(url=f"{base_url}/miniapp")))
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


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
            await upsert_telegram_subscriber(repository, profile)
            await repository.commit()
        else:
            async with AsyncSessionLocal() as session:
                repository = SqlAlchemyPublicRepository(session)
                await upsert_telegram_subscriber(repository, profile)
                await repository.commit()

    await message.answer(
        "PitchCopyTrade запущен.\n"
        "Основной subscriber-flow переводится в Telegram.\n"
        "Доступные команды:\n"
        "/catalog - витрина стратегий и продуктов\n"
        "/buy <product_slug> - показать условия покупки\n"
        "/confirm_buy <product_slug> - создать заявку на оплату\n"
        "/feed - доступные рекомендации",
        reply_markup=_start_keyboard(),
    )


START_HANDLER = (handle_start, CommandStart())
