from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from datetime import datetime, timezone

from pitchcopytrade.bot.main import create_bot
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.session import AsyncSessionLocal
from pitchcopytrade.db.models.audit import AuditEvent
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore
from pitchcopytrade.db.models.enums import RecommendationStatus, SubscriptionStatus
from pitchcopytrade.payments.tbank import TBankAcquiringClient
from pitchcopytrade.services.notifications import (
    deliver_recommendation_notifications,
    deliver_recommendation_notifications_file,
    deliver_subscriber_reminders,
)
from pitchcopytrade.services.lifecycle import expire_due_payments, expire_due_subscriptions
from pitchcopytrade.services.payment_sync import sync_tbank_pending_payments
from pitchcopytrade.services.publishing import publish_due_recommendations

logger = logging.getLogger(__name__)

JobCallable = Callable[[], Awaitable[None]]


@dataclass(frozen=True)
class WorkerJob:
    name: str
    runner: JobCallable


async def run_scheduled_publish() -> None:
    if AsyncSessionLocal is None:
        store = FileDataStore()
        graph = FileDatasetGraph.load(store)
        current_time = datetime.now(timezone.utc)
        published = []
        for item in graph.recommendations.values():
            if (
                item.status == RecommendationStatus.SCHEDULED
                and item.scheduled_for is not None
                and item.scheduled_for <= current_time
            ):
                item.status = RecommendationStatus.PUBLISHED
                item.published_at = current_time
                item.scheduled_for = None
                published.append(item)
                graph.add(
                    AuditEvent(
                        actor_user_id=None,
                        entity_type="recommendation",
                        entity_id=item.id,
                        action="worker.scheduled_publish",
                        payload={"status": item.status.value},
                    )
                )
        if published:
            graph.save(store)
            bot = create_bot(get_settings().telegram.bot_token.get_secret_value())
            try:
                for item in published:
                    try:
                        await deliver_recommendation_notifications_file(
                            graph,
                            store,
                            item,
                            bot,
                            trigger="scheduled_publish",
                        )
                    except Exception:
                        logger.exception("Notification delivery failed for recommendation %s", item.id)
            finally:
                await bot.session.close()
        logger.info("scheduled_publish tick(file): %s published", len(published))
        return

    async with AsyncSessionLocal() as session:
        published = await publish_due_recommendations(session)
        if published:
            bot = create_bot(get_settings().telegram.bot_token.get_secret_value())
            try:
                for item in published:
                    try:
                        await deliver_recommendation_notifications(session, item, bot, trigger="scheduled_publish")
                    except Exception:
                        logger.exception("Notification delivery failed for recommendation %s", item.id)
            finally:
                await bot.session.close()
    logger.info("scheduled_publish tick: %s published", len(published))


async def run_payment_expiry_sync() -> None:
    settings = get_settings()
    if AsyncSessionLocal is None:
        expiry_stats = await expire_due_payments(None)
        if settings.payments.provider != "tbank":
            logger.info(
                "payment_expiry_sync tick(file): expired=%s cancelled=%s",
                expiry_stats.expired,
                expiry_stats.cancelled,
            )
            return
        client = TBankAcquiringClient(
            terminal_key=settings.payments.tinkoff_terminal_key.get_secret_value(),
            password=settings.payments.tinkoff_secret_key.get_secret_value(),
        )
        stats = await sync_tbank_pending_payments(None, client=client)
        logger.info(
            "payment_expiry_sync tick(file): expired=%s cancelled=%s checked=%s paid=%s failed=%s pending=%s",
            expiry_stats.expired,
            expiry_stats.cancelled,
            stats.checked,
            stats.paid,
            stats.failed,
            stats.pending,
        )
        return

    async with AsyncSessionLocal() as session:
        expiry_stats = await expire_due_payments(session)
        if settings.payments.provider != "tbank":
            logger.info(
                "payment_expiry_sync tick: expired=%s cancelled=%s",
                expiry_stats.expired,
                expiry_stats.cancelled,
            )
            return
        client = TBankAcquiringClient(
            terminal_key=settings.payments.tinkoff_terminal_key.get_secret_value(),
            password=settings.payments.tinkoff_secret_key.get_secret_value(),
        )
        stats = await sync_tbank_pending_payments(session, client=client)
    logger.info(
        "payment_expiry_sync tick: expired=%s cancelled=%s checked=%s paid=%s failed=%s pending=%s",
        expiry_stats.expired,
        expiry_stats.cancelled,
        stats.checked,
        stats.paid,
        stats.failed,
        stats.pending,
    )


async def run_subscription_expiry() -> None:
    if AsyncSessionLocal is None:
        stats = await expire_due_subscriptions(None)
        logger.info("subscription_expiry tick(file): expired=%s", stats.expired)
        return

    async with AsyncSessionLocal() as session:
        stats = await expire_due_subscriptions(session)
    logger.info("subscription_expiry tick: expired=%s", stats.expired)


async def run_reminder_jobs() -> None:
    bot = create_bot(get_settings().telegram.bot_token.get_secret_value())
    try:
        if AsyncSessionLocal is None:
            stats = await deliver_subscriber_reminders(None, bot)
            logger.info("reminder_jobs tick(file): sent=%s skipped=%s", stats.sent, stats.skipped)
            return

        async with AsyncSessionLocal() as session:
            stats = await deliver_subscriber_reminders(session, bot)
        logger.info("reminder_jobs tick: sent=%s skipped=%s", stats.sent, stats.skipped)
    finally:
        await bot.session.close()


WORKER_JOBS: tuple[WorkerJob, ...] = (
    WorkerJob(name="scheduled_publish", runner=run_scheduled_publish),
    WorkerJob(name="payment_expiry_sync", runner=run_payment_expiry_sync),
    WorkerJob(name="subscription_expiry", runner=run_subscription_expiry),
    WorkerJob(name="reminder_jobs", runner=run_reminder_jobs),
)
