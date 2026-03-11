from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging


logger = logging.getLogger(__name__)

JobCallable = Callable[[], Awaitable[None]]


@dataclass(frozen=True)
class WorkerJob:
    name: str
    runner: JobCallable


async def run_scheduled_publish() -> None:
    logger.debug("scheduled_publish tick")


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
