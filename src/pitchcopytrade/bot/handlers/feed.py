from __future__ import annotations

from aiogram.filters import Command
from aiogram.types import Message

from pitchcopytrade.auth.session import build_telegram_login_link_token
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.session import AsyncSessionLocal
from pitchcopytrade.services.acl import get_user_by_telegram_id, list_user_visible_recommendations, user_has_active_access


async def handle_feed(message: Message) -> None:
    telegram_user = message.from_user
    if telegram_user is None:
        await message.answer("Не удалось определить Telegram-пользователя.")
        return

    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(session, telegram_user.id)
        if user is None:
            await message.answer("Доступ не найден. Сначала свяжите Telegram с аккаунтом подписчика.")
            return

        has_access = await user_has_active_access(session, user_id=user.id)
        if not has_access:
            await message.answer("Активных подписок нет. После подтверждения оплаты рекомендации появятся автоматически.")
            return

        recommendations = await list_user_visible_recommendations(session, user_id=user.id, limit=5)
        if not recommendations:
            await message.answer("Активный доступ есть, но новых публикаций пока нет.")
            return

        lines = ["Ваши доступные рекомендации:"]
        for item in recommendations:
            title = item.title or item.strategy.title
            parts = [f"- {title}", item.strategy.title, item.status.value]
            if item.legs:
                first_leg = item.legs[0]
                instrument = first_leg.instrument.ticker if first_leg.instrument else "инструмент"
                parts.append(
                    f"{instrument} {first_leg.side.value if first_leg.side else 'n/a'} "
                    f"{first_leg.entry_from or 'n/a'}"
                )
            if item.attachments:
                parts.append(f"{len(item.attachments)} files")
            lines.append(" | ".join(parts))
        await message.answer("\n".join(lines))


async def handle_web(message: Message) -> None:
    telegram_user = message.from_user
    if telegram_user is None:
        await message.answer("Не удалось определить Telegram-пользователя.")
        return

    async with AsyncSessionLocal() as session:
        user = await get_user_by_telegram_id(session, telegram_user.id)
        if user is None:
            await message.answer("Профиль подписчика не найден. Начните с /start.")
            return

        token = build_telegram_login_link_token(user)
        base_url = get_settings().app.base_url
        await message.answer(
            "Ссылка для web fallback через Telegram auth:\n"
            f"{base_url}/tg-auth?token={token}"
        )


FEED_HANDLER = (handle_feed, Command("feed"))
WEB_HANDLER = (handle_web, Command("web"))
