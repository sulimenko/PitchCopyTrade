from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging

from pitchcopytrade.db.session import AsyncSessionLocal
from pitchcopytrade.services.publishing import publish_due_recommendations

logger = logging.getLogger(__name__)

JobCallable = Callable[[], Awaitable[None]]


@dataclass(frozen=True)
class WorkerJob:
    name: str
    runner: JobCallable


async def run_scheduled_publish() -> None:
    async with AsyncSessionLocal() as session:
        published = await publish_due_recommendations(session)
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
