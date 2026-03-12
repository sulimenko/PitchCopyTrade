from __future__ import annotations

from aiogram.filters import Command, CommandObject
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, WebAppInfo

from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.session import AsyncSessionLocal
from pitchcopytrade.repositories.public import FilePublicRepository, SqlAlchemyPublicRepository
from pitchcopytrade.services.public import (
    TelegramSubscriberProfile,
    create_telegram_stub_checkout,
    get_public_product_by_slug,
    list_public_strategies,
)


def _supports_webapp() -> bool:
    return get_settings().app.base_url.startswith("https://")


def _catalog_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="/catalog"), KeyboardButton(text="/status")],
        [KeyboardButton(text="/feed"), KeyboardButton(text="/web")],
    ]
    if _supports_webapp():
        keyboard[1].append(
            KeyboardButton(text="Mini App", web_app=WebAppInfo(url=f"{get_settings().app.base_url}/miniapp"))
        )
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def _buy_preview_keyboard(product_slug: str) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text=f"/confirm_buy {product_slug}")],
        [KeyboardButton(text="/catalog"), KeyboardButton(text="/status")],
        [KeyboardButton(text="/feed"), KeyboardButton(text="/web")],
    ]
    if _supports_webapp():
        keyboard.append([KeyboardButton(text="Mini App", web_app=WebAppInfo(url=f"{get_settings().app.base_url}/miniapp"))])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def _buy_confirm_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="/feed"), KeyboardButton(text="/status")],
        [KeyboardButton(text="/catalog"), KeyboardButton(text="/web")],
    ]
    if _supports_webapp():
        keyboard[1].append(
            KeyboardButton(text="Mini App", web_app=WebAppInfo(url=f"{get_settings().app.base_url}/miniapp"))
        )
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


async def handle_catalog(message: Message) -> None:
    if AsyncSessionLocal is None:
        strategies = await list_public_strategies(FilePublicRepository())
    else:
        async with AsyncSessionLocal() as session:
            strategies = await list_public_strategies(SqlAlchemyPublicRepository(session))

    if not strategies:
        await message.answer("Публичных стратегий пока нет.")
        return

    lines = ["Витрина стратегий и продуктов:"]
    for strategy in strategies[:8]:
        lines.append(f"{strategy.title} | {strategy.author.display_name}")
        for product in strategy.subscription_products[:3]:
            lines.append(f"  - {product.slug}: {product.title} | {product.price_rub} RUB")
    lines.append("")
    lines.append("Для оформления используйте: /buy <product_slug>")
    lines.append("Для проверки доступа и оплат используйте: /status")
    await message.answer(
        "\n".join(lines),
        reply_markup=_catalog_keyboard(),
    )


async def handle_buy_preview(message: Message, command: CommandObject) -> None:
    product_slug = (command.args or "").strip()
    if not product_slug:
        await message.answer("Укажите slug продукта: /buy <product_slug>")
        return

    if AsyncSessionLocal is None:
        product = await get_public_product_by_slug(FilePublicRepository(), product_slug)
    else:
        async with AsyncSessionLocal() as session:
            product = await get_public_product_by_slug(SqlAlchemyPublicRepository(session), product_slug)

    if product is None:
        await message.answer("Продукт не найден или недоступен.")
        return

    lines = [
        f"Продукт: {product.title}",
        f"Цена: {product.price_rub} RUB",
        f"Период: {product.billing_period.value}",
        "Оплата сейчас работает как stub/manual.",
        "Отправляя confirm-команду, вы подтверждаете юридические документы, активные в системе.",
        f"Для продолжения отправьте: /confirm_buy {product.slug}",
    ]
    await message.answer(
        "\n".join(lines),
        reply_markup=_buy_preview_keyboard(product.slug),
    )


async def handle_buy_confirm(message: Message, command: CommandObject) -> None:
    telegram_user = message.from_user
    product_slug = (command.args or "").strip()
    if telegram_user is None:
        await message.answer("Не удалось определить Telegram-пользователя.")
        return
    if not product_slug:
        await message.answer("Укажите slug продукта: /confirm_buy <product_slug>")
        return

    if AsyncSessionLocal is None:
        repository = FilePublicRepository()
        product = await get_public_product_by_slug(repository, product_slug)
        if product is None:
            await message.answer("Продукт не найден или недоступен.")
            return
        try:
            result = await create_telegram_stub_checkout(
                repository,
                product=product,
                profile=TelegramSubscriberProfile(
                    telegram_user_id=telegram_user.id,
                    username=telegram_user.username,
                    first_name=telegram_user.first_name,
                    last_name=telegram_user.last_name,
                    lead_source_name="telegram_bot",
                ),
            )
        except ValueError as exc:
            await message.answer(str(exc))
            return
    else:
        async with AsyncSessionLocal() as session:
            repository = SqlAlchemyPublicRepository(session)
            product = await get_public_product_by_slug(repository, product_slug)
            if product is None:
                await message.answer("Продукт не найден или недоступен.")
                return

            try:
                result = await create_telegram_stub_checkout(
                    repository,
                    product=product,
                    profile=TelegramSubscriberProfile(
                        telegram_user_id=telegram_user.id,
                        username=telegram_user.username,
                        first_name=telegram_user.first_name,
                        last_name=telegram_user.last_name,
                        lead_source_name="telegram_bot",
                    ),
                )
            except ValueError as exc:
                await message.answer(str(exc))
                return

    await message.answer(
        "Заявка на оплату создана.\n"
        f"Продукт: {product.title}\n"
        f"Сумма: {result.payment.final_amount_rub} RUB\n"
        f"Reference: {result.payment.stub_reference}\n"
        "После подтверждения администратором доступ будет активирован.",
        reply_markup=_buy_confirm_keyboard(),
    )


CATALOG_HANDLER = (handle_catalog, Command("catalog"))
BUY_PREVIEW_HANDLER = (handle_buy_preview, Command("buy"))
BUY_CONFIRM_HANDLER = (handle_buy_confirm, Command("confirm_buy"))
