from __future__ import annotations

from aiogram.filters import Command
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, WebAppInfo

from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.session import AsyncSessionLocal
from pitchcopytrade.repositories.access import FileAccessRepository, SqlAlchemyAccessRepository
from pitchcopytrade.services.acl import get_user_by_telegram_id, list_user_visible_recommendations, user_has_active_access
from pitchcopytrade.services.subscriber import (
    build_subscriber_payments_message,
    build_subscriber_status_message,
    build_subscriber_subscriptions_message,
    build_subscriber_web_message,
    get_subscriber_status_snapshot,
)


def _supports_webapp() -> bool:
    return get_settings().app.base_url.startswith("https://")


def _subscriber_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="/status"), KeyboardButton(text="/feed")],
        [KeyboardButton(text="/subscriptions"), KeyboardButton(text="/payments")],
        [KeyboardButton(text="/catalog"), KeyboardButton(text="/web")],
    ]
    if _supports_webapp():
        keyboard[2].append(
            KeyboardButton(text="Mini App", web_app=WebAppInfo(url=f"{get_settings().app.base_url}/miniapp"))
        )
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


async def handle_feed(message: Message) -> None:
    telegram_user = message.from_user
    if telegram_user is None:
        await message.answer("Не удалось определить Telegram-пользователя.")
        return

    if AsyncSessionLocal is None:
        repository = FileAccessRepository()
        user = await get_user_by_telegram_id(repository, telegram_user.id)
        if user is None:
            await message.answer(
                "Доступ не найден. Сначала выполните /start, затем оформите подписку через /catalog.",
                reply_markup=_subscriber_keyboard(),
            )
            return

        has_access = await user_has_active_access(repository, user_id=user.id)
        if not has_access:
            await message.answer(
                "Активных подписок нет. После подтверждения оплаты рекомендации появятся автоматически. "
                "Проверить текущий статус можно командой /status.",
                reply_markup=_subscriber_keyboard(),
            )
            return

        recommendations = await list_user_visible_recommendations(repository, user_id=user.id, limit=5)
        if not recommendations:
            await message.answer(
                "Активный доступ есть, но новых публикаций пока нет. "
                "Возвращайтесь в /feed позже или откройте Mini App.",
                reply_markup=_subscriber_keyboard(),
            )
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
        await message.answer("\n".join(lines), reply_markup=_subscriber_keyboard())
        return

    async with AsyncSessionLocal() as session:
        repository = SqlAlchemyAccessRepository(session)
        user = await get_user_by_telegram_id(repository, telegram_user.id)
        if user is None:
            await message.answer(
                "Доступ не найден. Сначала выполните /start, затем оформите подписку через /catalog.",
                reply_markup=_subscriber_keyboard(),
            )
            return

        has_access = await user_has_active_access(repository, user_id=user.id)
        if not has_access:
            await message.answer(
                "Активных подписок нет. После подтверждения оплаты рекомендации появятся автоматически. "
                "Проверить текущий статус можно командой /status.",
                reply_markup=_subscriber_keyboard(),
            )
            return

        recommendations = await list_user_visible_recommendations(repository, user_id=user.id, limit=5)
        if not recommendations:
            await message.answer(
                "Активный доступ есть, но новых публикаций пока нет. "
                "Возвращайтесь в /feed позже или откройте Mini App.",
                reply_markup=_subscriber_keyboard(),
            )
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
        await message.answer("\n".join(lines), reply_markup=_subscriber_keyboard())


async def handle_status(message: Message) -> None:
    telegram_user = message.from_user
    if telegram_user is None:
        await message.answer("Не удалось определить Telegram-пользователя.", reply_markup=_subscriber_keyboard())
        return

    if AsyncSessionLocal is None:
        repository = FileAccessRepository()
        snapshot = await get_subscriber_status_snapshot(repository, telegram_user_id=telegram_user.id)
    else:
        async with AsyncSessionLocal() as session:
            repository = SqlAlchemyAccessRepository(session)
            snapshot = await get_subscriber_status_snapshot(repository, telegram_user_id=telegram_user.id)

    if snapshot is None:
        await message.answer(
            "Профиль подписчика еще не создан. Начните с /start, затем откройте /catalog.",
            reply_markup=_subscriber_keyboard(),
        )
        return

    await message.answer(build_subscriber_status_message(snapshot), reply_markup=_subscriber_keyboard())


async def handle_web(message: Message) -> None:
    telegram_user = message.from_user
    if telegram_user is None:
        await message.answer("Не удалось определить Telegram-пользователя.")
        return

    if AsyncSessionLocal is None:
        repository = FileAccessRepository()
        user = await get_user_by_telegram_id(repository, telegram_user.id)
        if user is None:
            await message.answer("Профиль подписчика не найден. Начните с /start.", reply_markup=_subscriber_keyboard())
            return

        base_url = get_settings().app.base_url
        await message.answer(
            build_subscriber_web_message(user, base_url=base_url, include_webapp=_supports_webapp()),
            reply_markup=_subscriber_keyboard(),
        )
        return

    async with AsyncSessionLocal() as session:
        repository = SqlAlchemyAccessRepository(session)
        user = await get_user_by_telegram_id(repository, telegram_user.id)
        if user is None:
            await message.answer("Профиль подписчика не найден. Начните с /start.", reply_markup=_subscriber_keyboard())
            return

        base_url = get_settings().app.base_url
        await message.answer(
            build_subscriber_web_message(user, base_url=base_url, include_webapp=_supports_webapp()),
            reply_markup=_subscriber_keyboard(),
        )


async def handle_subscriptions(message: Message) -> None:
    telegram_user = message.from_user
    if telegram_user is None:
        await message.answer("Не удалось определить Telegram-пользователя.", reply_markup=_subscriber_keyboard())
        return

    if AsyncSessionLocal is None:
        repository = FileAccessRepository()
        snapshot = await get_subscriber_status_snapshot(repository, telegram_user_id=telegram_user.id)
    else:
        async with AsyncSessionLocal() as session:
            repository = SqlAlchemyAccessRepository(session)
            snapshot = await get_subscriber_status_snapshot(repository, telegram_user_id=telegram_user.id)

    if snapshot is None:
        await message.answer(
            "Профиль подписчика еще не создан. Начните с /start, затем откройте /catalog.",
            reply_markup=_subscriber_keyboard(),
        )
        return

    await message.answer(build_subscriber_subscriptions_message(snapshot), reply_markup=_subscriber_keyboard())


async def handle_payments(message: Message) -> None:
    telegram_user = message.from_user
    if telegram_user is None:
        await message.answer("Не удалось определить Telegram-пользователя.", reply_markup=_subscriber_keyboard())
        return

    if AsyncSessionLocal is None:
        repository = FileAccessRepository()
        snapshot = await get_subscriber_status_snapshot(repository, telegram_user_id=telegram_user.id)
    else:
        async with AsyncSessionLocal() as session:
            repository = SqlAlchemyAccessRepository(session)
            snapshot = await get_subscriber_status_snapshot(repository, telegram_user_id=telegram_user.id)

    if snapshot is None:
        await message.answer(
            "Профиль подписчика еще не создан. Начните с /start, затем откройте /catalog.",
            reply_markup=_subscriber_keyboard(),
        )
        return

    await message.answer(build_subscriber_payments_message(snapshot), reply_markup=_subscriber_keyboard())


FEED_HANDLER = (handle_feed, Command("feed"))
STATUS_HANDLER = (handle_status, Command("status"))
SUBSCRIPTIONS_HANDLER = (handle_subscriptions, Command("subscriptions"))
PAYMENTS_HANDLER = (handle_payments, Command("payments"))
WEB_HANDLER = (handle_web, Command("web"))
VERIFY_HANDLER = (handle_web, Command("verify"))
