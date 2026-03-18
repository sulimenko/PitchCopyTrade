from __future__ import annotations

import asyncio
import hmac
import logging
from typing import Any

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from pitchcopytrade.bot.dispatcher import build_dispatcher
from pitchcopytrade.core.runtime import bootstrap_runtime

logger = logging.getLogger(__name__)


def create_bot(token: str) -> Bot:
    return Bot(token=token)


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

    recommendation_id = body.get("recommendation_id")
    if not recommendation_id:
        return web.json_response({"detail": "recommendation_id required"}, status=400)

    bot: Bot = request.app["bot"]
    await _broadcast_recommendation(bot, settings, recommendation_id)
    return web.json_response({"status": "ok"})


async def _broadcast_recommendation(bot: Bot, settings: Any, recommendation_id: str) -> None:
    from pitchcopytrade.db.session import AsyncSessionLocal
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from pitchcopytrade.db.models.content import Recommendation, RecommendationLeg
    from pitchcopytrade.db.models.catalog import Strategy, SubscriptionProduct
    from pitchcopytrade.db.models.commerce import Subscription
    from pitchcopytrade.db.models.enums import SubscriptionStatus

    if AsyncSessionLocal is None:
        logger.warning("No DB session, skipping broadcast")
        return

    async with AsyncSessionLocal() as session:
        rec_result = await session.execute(
            select(Recommendation)
            .options(
                selectinload(Recommendation.legs).selectinload(RecommendationLeg.instrument),
                selectinload(Recommendation.strategy),
            )
            .where(Recommendation.id == recommendation_id)
        )
        rec = rec_result.scalar_one_or_none()
        if rec is None:
            logger.warning("Recommendation %s not found", recommendation_id)
            return

        strategy: Strategy = rec.strategy

        subs_result = await session.execute(
            select(Subscription)
            .join(SubscriptionProduct, Subscription.product_id == SubscriptionProduct.id)
            .options(selectinload(Subscription.user))
            .where(
                SubscriptionProduct.strategy_id == strategy.id,
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
        )
        subscriptions = subs_result.scalars().all()

        text = _format_recommendation(rec, strategy)

        for sub in subscriptions:
            user = sub.user
            if user and user.telegram_user_id:
                try:
                    await bot.send_message(chat_id=user.telegram_user_id, text=text)
                    logger.info("Sent broadcast to user %s", user.telegram_user_id)
                except Exception as exc:
                    logger.error("Failed to send to user %s: %s", user.telegram_user_id, exc)


def _format_recommendation(rec: Any, strategy: Any) -> str:
    lines = [f"Новая рекомендация — {strategy.title}"]
    if rec.title:
        lines.append(rec.title)
    lines.append("")
    for leg in rec.legs:
        ticker = leg.instrument.ticker if leg.instrument else "—"
        side = leg.side.upper() if leg.side else "—"
        entry = leg.entry_from or "рынок"
        tp = leg.take_profit_1 or "—"
        sl = leg.stop_loss or "—"
        lines.append(f"{ticker} — {side} @ {entry}")
        lines.append(f"Цель: {tp}")
        lines.append(f"Стоп: {sl}")
    if rec.summary:
        lines.append("")
        lines.append(rec.summary)
    return "\n".join(lines)


async def run_bot() -> None:
    settings = bootstrap_runtime("bot")

    dp: Dispatcher = build_dispatcher()
    bot = create_bot(settings.telegram.bot_token.get_secret_value())

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
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run_bot())
