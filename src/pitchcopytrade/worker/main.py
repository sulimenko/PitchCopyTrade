from __future__ import annotations

import asyncio
import logging

from pitchcopytrade.core.runtime import bootstrap_runtime
from pitchcopytrade.worker.jobs.placeholders import PLACEHOLDER_JOBS

logger = logging.getLogger(__name__)


async def run_worker() -> None:
    bootstrap_runtime("worker")
    logger.info("Worker foundation process started with jobs: %s", ", ".join(PLACEHOLDER_JOBS))
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(run_worker())
