from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from datetime import datetime, timezone

from pitchcopytrade.bot.main import create_bot
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.session import AsyncSessionLocal
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore
from pitchcopytrade.db.models.enums import RecommendationStatus, SubscriptionStatus
from pitchcopytrade.services.notifications import build_recommendation_notification_text, deliver_recommendation_notifications
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
        if published:
            graph.save(store)
            bot = create_bot(get_settings().telegram.bot_token.get_secret_value())
            try:
                for item in published:
                    recipients = {
                        subscription.user.telegram_user_id
                        for subscription in graph.subscriptions.values()
                        if subscription.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL)
                        and subscription.user.telegram_user_id is not None
                        and (
                            subscription.product.strategy_id == item.strategy_id
                            or subscription.product.author_id == item.author_id
                            or (
                                subscription.product.bundle_id is not None
                                and any(
                                    member.bundle_id == subscription.product.bundle_id and member.strategy_id == item.strategy_id
                                    for member in graph.bundle_members
                                )
                            )
                        )
                    }
                    text = build_recommendation_notification_text(item)
                    for chat_id in recipients:
                        try:
                            await bot.send_message(int(chat_id), text)
                        except Exception:
                            logger.exception("Failed to deliver file-mode recommendation notification to chat_id=%s", chat_id)
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
                    await deliver_recommendation_notifications(session, item, bot)
            finally:
                await bot.session.close()
    logger.info("scheduled_publish tick: %s published", len(published))


async def run_payment_expiry_sync() -> None:
    logger.debug("payment_expiry_sync tick")


async def run_subscription_expiry() -> None:
    logger.debug("subscription_expiry tick")


async def run_reminder_jobs() -> None:
    logger.debug("reminder_jobs tick")


WORKER_JOBS: tuple[WorkerJob, ...] = (
    WorkerJob(name="scheduled_publish", runner=run_scheduled_publish),
    WorkerJob(name="payment_expiry_sync", runner=run_payment_expiry_sync),
    WorkerJob(name="subscription_expiry", runner=run_subscription_expiry),
    WorkerJob(name="reminder_jobs", runner=run_reminder_jobs),
)
