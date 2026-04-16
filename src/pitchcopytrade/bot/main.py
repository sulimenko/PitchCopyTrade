from __future__ import annotations

import argparse
import asyncio
import hmac
import logging
from html import escape
from typing import Any

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError, TelegramUnauthorizedError
from aiogram.client.default import DefaultBotProperties
from aiogram.methods import GetMe
from aiogram.enums import ParseMode
from aiogram.types import MenuButtonWebApp, WebAppInfo
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from pitchcopytrade.bot.dispatcher import build_dispatcher
from pitchcopytrade.core.runtime import bootstrap_runtime
from pitchcopytrade.core.runtime import secret_fingerprint
from pitchcopytrade.services.notifications import deliver_message_notifications_by_id

logger = logging.getLogger(__name__)
DEFAULT_POLLING_RETRY_DELAY_SECONDS = 2
MAX_POLLING_RETRY_DELAY_SECONDS = 60


def create_bot(token: str) -> Bot:
    return Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


async def _handle_health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def _handle_internal_broadcast(request: web.Request) -> web.Response:
    settings = request.app["settings"]
    secret = settings.internal_api_secret.get_secret_value()
    token = request.headers.get("X-Internal-Token", "")
    if not hmac.compare_digest(token, secret):
        return web.json_response({"detail": "Unauthorized"}, status=401)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"detail": "Invalid JSON"}, status=400)

    message_id = body.get("message_id") or body.get("recommendation_id")
    if not message_id:
        return web.json_response({"detail": "message_id required"}, status=400)

    bot: Bot = request.app["bot"]
    await _broadcast_message(bot, settings, message_id)
    return web.json_response({"status": "ok"})


async def _broadcast_message(bot: Bot, settings: Any, message_id: str) -> None:
    from pitchcopytrade.db.session import AsyncSessionLocal

    if AsyncSessionLocal is None:
        logger.warning("No DB session, skipping broadcast")
        return

    async with AsyncSessionLocal() as session:
        delivered = await deliver_message_notifications_by_id(session, message_id, bot, trigger="internal_broadcast")
        logger.info("Sent broadcast message %s to %d telegram recipient(s)", message_id, len(delivered or []))


async def _configure_catalog_menu_button(bot: Bot, settings: Any) -> None:
    base_url = str(getattr(settings.app, "base_url", "") or "").rstrip("/")
    if not base_url.startswith("https://"):
        logger.warning("Skipping Telegram menu button setup: BASE_URL is not HTTPS (%s)", base_url or "empty")
        return
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Открыть каталог",
                web_app=WebAppInfo(url=f"{base_url}/app/catalog"),
            )
        )
        logger.info("Telegram menu button configured for catalog")
    except Exception as exc:
        logger.warning("Unable to configure Telegram menu button: %s", exc)


def _format_message(rec: Any, strategy: Any) -> str:
    lines = [f"<b>Новая публикация</b> — {escape(strategy.title)}"]
    if rec.title:
        lines.append(f"<b>{escape(rec.title)}</b>")
    text_payload = rec.text or {}
    body = text_payload.get("body") or text_payload.get("plain")
    if body:
        lines.append("")
        lines.append(str(body))
    if rec.deals:
        lines.append("")
        for deal in rec.deals:
            lines.append(
                f"{escape(str(deal.get('ticker') or deal.get('instrument') or deal.get('instrument_id') or '—'))} — "
                f"{escape(str(deal.get('side') or '—'))}"
            )
    return "\n".join(lines)


def _is_retryable_bot_transport_error(exc: BaseException) -> bool:
    return isinstance(exc, (TelegramNetworkError, OSError, TimeoutError, asyncio.TimeoutError))


def _is_fatal_bot_polling_error(exc: BaseException) -> bool:
    return isinstance(exc, (TelegramUnauthorizedError, TelegramBadRequest))


def _polling_retry_delay(attempt: int) -> int:
    exponent = max(0, attempt - 1)
    return min(DEFAULT_POLLING_RETRY_DELAY_SECONDS * (2**exponent), MAX_POLLING_RETRY_DELAY_SECONDS)


async def run_bot_smoke_check(bot: Bot) -> Any:
    me = await bot.get_me()
    logger.info("Telegram smoke check ok: id=%s username=%s", getattr(me, "id", None), getattr(me, "username", None))
    return me


async def run_polling_with_backoff(
    dp: Dispatcher,
    bot: Bot,
    *,
    sleep_func: Any = asyncio.sleep,
) -> None:
    attempt = 0
    while True:
        try:
            await run_bot_smoke_check(bot)
            if attempt:
                logger.info("Telegram polling recovered after %s retry attempt(s)", attempt)
            await dp.start_polling(bot, close_bot_session=False)
            logger.info("Telegram polling stopped gracefully")
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if _is_retryable_bot_transport_error(exc):
                attempt += 1
                delay_seconds = _polling_retry_delay(attempt)
                logger.warning(
                    "Telegram transport failure during polling/getMe; retrying in %ss attempt=%s error=%s",
                    delay_seconds,
                    attempt,
                    exc,
                )
                await sleep_func(delay_seconds)
                continue
            if _is_fatal_bot_polling_error(exc):
                logger.exception("Fatal Telegram bot polling error; stopping bot process")
                raise
            logger.exception("Unhandled Telegram bot polling error; stopping bot process")
            raise


async def run_bot() -> None:
    settings = bootstrap_runtime("bot")

    dp: Dispatcher = build_dispatcher()
    bot = create_bot(settings.telegram.bot_token.get_secret_value())
    logger.info(
        "Bot startup complete: telegram_bot_username=%s telegram_bot_token_fingerprint=%s mode=%s",
        settings.telegram.bot_username,
        secret_fingerprint(settings.telegram.bot_token.get_secret_value()),
        "webhook" if settings.telegram.use_webhook else "polling",
    )
    await _configure_catalog_menu_button(bot, settings)

    if settings.telegram.use_webhook:
        logger.info("Starting bot in webhook mode on port 8080")
        webhook_url = settings.telegram_webhook_url
        if webhook_url:
            await bot.set_webhook(
                url=webhook_url,
                secret_token=settings.telegram.webhook_secret.get_secret_value(),
            )
            logger.info("Webhook registered: %s", webhook_url)

        app = web.Application()
        app["bot"] = bot
        app["settings"] = settings

        app.router.add_get("/health", _handle_health)
        app.router.add_post("/internal/broadcast", _handle_internal_broadcast)

        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook/bot")
        setup_application(app, dp, bot=bot)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 8080)
        await site.start()
        logger.info("Bot webhook server started on port 8080")

        try:
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()
    else:
        logger.info("Starting bot polling")
        try:
            await run_polling_with_backoff(dp, bot)
        finally:
            await bot.session.close()


async def run_bot_cli(*, smoke_check: bool = False) -> None:
    settings = bootstrap_runtime("bot")
    bot = create_bot(settings.telegram.bot_token.get_secret_value())
    if smoke_check:
        try:
            await run_bot_smoke_check(bot)
        finally:
            await bot.session.close()
        return
    await run_bot()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PitchCopyTrade Telegram bot runtime")
    parser.add_argument("--smoke-check", action="store_true", help="Run Telegram connectivity smoke check via getMe and exit")
    args = parser.parse_args()
    asyncio.run(run_bot_cli(smoke_check=args.smoke_check))
