from __future__ import annotations

import asyncio
import logging

from pitchcopytrade.core.runtime import bootstrap_runtime
from pitchcopytrade.worker.runner import get_worker_jobs, run_worker_loop

logger = logging.getLogger(__name__)


async def run_worker() -> None:
    bootstrap_runtime("worker")
    jobs = get_worker_jobs()
    logger.info("Worker foundation process started with jobs: %s", ", ".join(job.name for job in jobs))
    await run_worker_loop()


if __name__ == "__main__":
    asyncio.run(run_worker())
