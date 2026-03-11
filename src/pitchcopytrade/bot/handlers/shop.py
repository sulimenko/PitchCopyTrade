from __future__ import annotations

from aiogram.filters import Command, CommandObject
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from pitchcopytrade.db.session import AsyncSessionLocal
from pitchcopytrade.services.public import (
    TelegramSubscriberProfile,
    create_telegram_stub_checkout,
    get_public_product_by_slug,
    list_public_strategies,
)


async def handle_catalog(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        strategies = await list_public_strategies(session)

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
    await message.answer(
        "\n".join(lines),
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="/catalog"), KeyboardButton(text="/feed")],
                [KeyboardButton(text="/web")],
            ],
            resize_keyboard=True,
        ),
    )


async def handle_buy_preview(message: Message, command: CommandObject) -> None:
    product_slug = (command.args or "").strip()
    if not product_slug:
        await message.answer("Укажите slug продукта: /buy <product_slug>")
        return

    async with AsyncSessionLocal() as session:
        product = await get_public_product_by_slug(session, product_slug)

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
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=f"/confirm_buy {product.slug}")],
                [KeyboardButton(text="/catalog"), KeyboardButton(text="/web")],
            ],
            resize_keyboard=True,
        ),
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

    async with AsyncSessionLocal() as session:
        product = await get_public_product_by_slug(session, product_slug)
        if product is None:
            await message.answer("Продукт не найден или недоступен.")
            return

        try:
            result = await create_telegram_stub_checkout(
                session,
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
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="/feed"), KeyboardButton(text="/web")],
                [KeyboardButton(text="/catalog")],
            ],
            resize_keyboard=True,
        ),
    )


CATALOG_HANDLER = (handle_catalog, Command("catalog"))
BUY_PREVIEW_HANDLER = (handle_buy_preview, Command("buy"))
BUY_CONFIRM_HANDLER = (handle_buy_confirm, Command("confirm_buy"))
