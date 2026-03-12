from __future__ import annotations

from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

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
        [KeyboardButton(text="/subscriptions"), KeyboardButton(text="/payments")],
        [KeyboardButton(text="/feed"), KeyboardButton(text="/web")],
    ]
    if _supports_webapp():
        keyboard[2].append(
            KeyboardButton(text="Mini App", web_app=WebAppInfo(url=f"{get_settings().app.base_url}/miniapp"))
        )
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def _catalog_inline_keyboard(strategies) -> InlineKeyboardMarkup | None:
    rows: list[list[InlineKeyboardButton]] = []
    for strategy in strategies[:6]:
        for product in strategy.subscription_products[:1]:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"{strategy.title}: {product.price_rub} RUB",
                        callback_data=f"buy_preview:{product.slug}",
                    )
                ]
            )
    if not rows:
        return None
    rows.append([InlineKeyboardButton(text="Обновить каталог", callback_data="shop_catalog")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _buy_preview_keyboard(product_slug: str) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text=f"/confirm_buy {product_slug}")],
        [KeyboardButton(text="/catalog"), KeyboardButton(text="/status")],
        [KeyboardButton(text="/subscriptions"), KeyboardButton(text="/payments")],
        [KeyboardButton(text="/feed"), KeyboardButton(text="/web")],
    ]
    if _supports_webapp():
        keyboard.append([KeyboardButton(text="Mini App", web_app=WebAppInfo(url=f"{get_settings().app.base_url}/miniapp"))])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def _buy_confirm_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="/feed"), KeyboardButton(text="/status")],
        [KeyboardButton(text="/subscriptions"), KeyboardButton(text="/payments")],
        [KeyboardButton(text="/catalog"), KeyboardButton(text="/web")],
    ]
    if _supports_webapp():
        keyboard[2].append(
            KeyboardButton(text="Mini App", web_app=WebAppInfo(url=f"{get_settings().app.base_url}/miniapp"))
        )
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def _buy_preview_inline_keyboard(product_slug: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Создать заявку", callback_data=f"buy_confirm:{product_slug}")],
            [InlineKeyboardButton(text="Назад к каталогу", callback_data="shop_catalog")],
        ]
    )


def _catalog_text(strategies) -> str:
    lines = ["Витрина стратегий и продуктов:"]
    for strategy in strategies[:8]:
        lines.append(f"{strategy.title} | {strategy.author.display_name}")
        for product in strategy.subscription_products[:3]:
            lines.append(f"  - {product.slug}: {product.title} | {product.price_rub} RUB")
    lines.append("")
    lines.append("Для оформления используйте: /buy <product_slug>")
    lines.append("Для проверки доступа и оплат используйте: /status")
    lines.append("Для списка подписок: /subscriptions")
    return "\n".join(lines)


def _buy_preview_text(product) -> str:
    return "\n".join(
        [
            f"Продукт: {product.title}",
            f"Цена: {product.price_rub} RUB",
            f"Период: {product.billing_period.value}",
            "Оплата сейчас работает как stub/manual.",
            "Отправляя confirm-команду, вы подтверждаете юридические документы, активные в системе.",
            f"Для продолжения отправьте: /confirm_buy {product.slug}",
            "Или нажмите inline-кнопку ниже.",
        ]
    )


async def handle_catalog(message: Message) -> None:
    if AsyncSessionLocal is None:
        strategies = await list_public_strategies(FilePublicRepository())
    else:
        async with AsyncSessionLocal() as session:
            strategies = await list_public_strategies(SqlAlchemyPublicRepository(session))

    if not strategies:
        await message.answer("Публичных стратегий пока нет.")
        return

    await message.answer(_catalog_text(strategies), reply_markup=_catalog_keyboard())
    inline_keyboard = _catalog_inline_keyboard(strategies)
    if inline_keyboard is not None:
        await message.answer("Быстрый выбор продукта:", reply_markup=inline_keyboard)


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

    await message.answer(
        _buy_preview_text(product),
        reply_markup=_buy_preview_inline_keyboard(product.slug),
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
        + (
            f"Оплата по СБП: {result.payment_url}\n"
            "После успешной оплаты статус обновится в системе."
            if getattr(result, "payment_url", None)
            else "После подтверждения администратором доступ будет активирован."
        ),
        reply_markup=_buy_confirm_keyboard(),
    )


async def handle_shop_callback(callback: CallbackQuery) -> None:
    data = callback.data or ""
    message = callback.message
    if message is None:
        await callback.answer()
        return

    if data == "shop_catalog":
        await handle_catalog(message)
        await callback.answer("Каталог обновлен")
        return

    if data.startswith("buy_preview:"):
        slug = data.split(":", 1)[1]
        await handle_buy_preview(message, CommandObject(prefix="/", command="buy", mention=None, args=slug))
        await callback.answer("Открыто описание продукта")
        return

    if data.startswith("buy_confirm:"):
        slug = data.split(":", 1)[1]
        await handle_buy_confirm(message, CommandObject(prefix="/", command="confirm_buy", mention=None, args=slug))
        await callback.answer("Заявка создана")
        return

    await callback.answer()


CATALOG_HANDLER = (handle_catalog, Command("catalog"))
BUY_PREVIEW_HANDLER = (handle_buy_preview, Command("buy"))
BUY_CONFIRM_HANDLER = (handle_buy_confirm, Command("confirm_buy"))
SHOP_CALLBACK_HANDLER = handle_shop_callback
