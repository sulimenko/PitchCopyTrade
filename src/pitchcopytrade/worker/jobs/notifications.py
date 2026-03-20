from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def send_recommendation_notifications(ctx: dict, recommendation_id: str) -> None:
    from pitchcopytrade.core.config import get_settings
    from pitchcopytrade.db.session import AsyncSessionLocal

    if AsyncSessionLocal is None:
        logger.warning("No DB session, skipping notifications for %s", recommendation_id)
        return

    settings = get_settings()

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from pitchcopytrade.db.models.content import Recommendation, RecommendationLeg
        from pitchcopytrade.db.models.catalog import Strategy, SubscriptionProduct
        from pitchcopytrade.db.models.commerce import Subscription
        from pitchcopytrade.db.models.enums import SubscriptionStatus
        from pitchcopytrade.db.models.notification_log import NotificationChannelEnum, NotificationLog

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
                Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]),
            )
        )
        subscriptions = list(subs_result.scalars().all())
        logger.info("Broadcasting recommendation %s to %d subscribers", recommendation_id, len(subscriptions))

        text_tg = _format_telegram_message(rec, strategy)
        email_subject = f"Новая рекомендация — {strategy.title}"

        for sub in subscriptions:
            user = sub.user
            if user is None:
                continue

            # Telegram notification via internal bot API
            if user.telegram_user_id:
                success, error = await _send_telegram(settings, recommendation_id, user.telegram_user_id, text_tg)
                log = NotificationLog(
                    recommendation_id=recommendation_id,
                    user_id=user.id,
                    channel=NotificationChannelEnum.TELEGRAM,
                    sent_at=datetime.now(timezone.utc),
                    success=success,
                    error_detail=error,
                )
                session.add(log)

            # Email notification
            if user.email:
                success, error = await _send_email(settings, user.email, email_subject, rec, strategy)
                log = NotificationLog(
                    recommendation_id=recommendation_id,
                    user_id=user.id,
                    channel=NotificationChannelEnum.EMAIL,
                    sent_at=datetime.now(timezone.utc),
                    success=success,
                    error_detail=error,
                )
                session.add(log)

        await session.commit()


async def _send_telegram(settings, recommendation_id: str, telegram_user_id: int, text: str) -> tuple[bool, str | None]:
    import httpx
    bot_internal_url = "http://bot:8080/internal/broadcast"
    secret = settings.internal_api_secret.get_secret_value()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                bot_internal_url,
                json={"recommendation_id": recommendation_id},
                headers={"X-Internal-Token": secret},
            )
            if resp.status_code == 200:
                return True, None
            return False, f"HTTP {resp.status_code}"
    except Exception as exc:
        logger.error("Telegram notification failed: %s", exc)
        return False, str(exc)


async def _send_email(settings, email: str, subject: str, rec, strategy) -> tuple[bool, str | None]:
    try:
        import aiosmtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from}>"
        msg["To"] = email

        text_body = _format_email_text(rec, strategy)
        html_body = _format_email_html(rec, strategy)

        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            use_tls=settings.smtp_ssl,
            username=settings.smtp_user,
            password=settings.smtp_password.get_secret_value(),
        )
        return True, None
    except Exception as exc:
        logger.error("Email notification to %s failed: %s", email, exc)
        return False, str(exc)


def _format_telegram_message(rec, strategy) -> str:
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


def _format_email_text(rec, strategy) -> str:
    return _format_telegram_message(rec, strategy)


def _format_email_html(rec, strategy) -> str:
    lines = [f"<p><strong>Новая рекомендация — {strategy.title}</strong></p>"]
    if rec.title:
        lines.append(f"<p>{rec.title}</p>")
    for leg in rec.legs:
        ticker = leg.instrument.ticker if leg.instrument else "—"
        side = (leg.side.value.upper() if leg.side else "—")
        entry = leg.entry_from or "рынок"
        tp = leg.take_profit_1 or "—"
        sl = leg.stop_loss or "—"
        lines.append(f"<p><strong>{ticker}</strong> — {side} @ {entry}<br/>Цель: {tp}<br/>Стоп: {sl}</p>")
    if rec.summary:
        lines.append(f"<p>{rec.summary}</p>")
    return "".join(lines)
