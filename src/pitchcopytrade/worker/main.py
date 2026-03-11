from __future__ import annotations

import asyncio
import logging

from pitchcopytrade.core.logging import configure_logging
from pitchcopytrade.worker.jobs.placeholders import PLACEHOLDER_JOBS

configure_logging()
logger = logging.getLogger(__name__)


async def run_worker() -> None:
    logger.info("Worker foundation process started with jobs: %s", ", ".join(PLACEHOLDER_JOBS))
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(run_worker())
