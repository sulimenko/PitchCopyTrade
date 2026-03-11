from __future__ import annotations

from aiogram.filters import CommandStart
from aiogram.types import Message

from pitchcopytrade.db.session import AsyncSessionLocal
from pitchcopytrade.services.public import TelegramSubscriberProfile, upsert_telegram_subscriber


async def handle_start(message: Message) -> None:
    telegram_user = message.from_user
    if telegram_user is not None:
        async with AsyncSessionLocal() as session:
            await upsert_telegram_subscriber(
                session,
                TelegramSubscriberProfile(
                    telegram_user_id=telegram_user.id,
                    username=telegram_user.username,
                    first_name=telegram_user.first_name,
                    last_name=telegram_user.last_name,
                ),
            )
            await session.commit()

    await message.answer(
        "PitchCopyTrade запущен.\n"
        "Основной subscriber-flow переводится в Telegram.\n"
        "Доступные команды:\n"
        "/catalog - витрина стратегий и продуктов\n"
        "/buy <product_slug> - показать условия покупки\n"
        "/confirm_buy <product_slug> - создать заявку на оплату\n"
        "/feed - доступные рекомендации"
    )


START_HANDLER = (handle_start, CommandStart())
