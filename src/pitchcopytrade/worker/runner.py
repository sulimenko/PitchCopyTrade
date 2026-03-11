from __future__ import annotations

import asyncio
import logging

from pitchcopytrade.worker.jobs.placeholders import WORKER_JOBS, WorkerJob


logger = logging.getLogger(__name__)
DEFAULT_WORKER_SLEEP_SECONDS = 3600


def get_worker_jobs() -> tuple[WorkerJob, ...]:
    return WORKER_JOBS


async def run_worker_once() -> None:
    for job in get_worker_jobs():
        logger.info("Running worker job: %s", job.name)
        await job.runner()


async def run_worker_loop(sleep_seconds: int = DEFAULT_WORKER_SLEEP_SECONDS) -> None:
    while True:
        await run_worker_once()
        await asyncio.sleep(sleep_seconds)
