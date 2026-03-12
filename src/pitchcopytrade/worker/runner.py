from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from time import perf_counter

from pitchcopytrade.worker.jobs.placeholders import WORKER_JOBS, WorkerJob


logger = logging.getLogger(__name__)
DEFAULT_WORKER_SLEEP_SECONDS = 3600


@dataclass(frozen=True)
class WorkerJobResult:
    name: str
    ok: bool
    duration_ms: int


def get_worker_jobs() -> tuple[WorkerJob, ...]:
    return WORKER_JOBS


async def run_worker_once() -> list[WorkerJobResult]:
    results: list[WorkerJobResult] = []
    for job in get_worker_jobs():
        started = perf_counter()
        logger.info("Running worker job: %s", job.name)
        try:
            await job.runner()
        except Exception:
            duration_ms = int((perf_counter() - started) * 1000)
            logger.exception("Worker job failed: %s duration_ms=%s", job.name, duration_ms)
            results.append(WorkerJobResult(name=job.name, ok=False, duration_ms=duration_ms))
            continue
        duration_ms = int((perf_counter() - started) * 1000)
        logger.info("Worker job finished: %s duration_ms=%s", job.name, duration_ms)
        results.append(WorkerJobResult(name=job.name, ok=True, duration_ms=duration_ms))
    return results


async def run_worker_loop(sleep_seconds: int = DEFAULT_WORKER_SLEEP_SECONDS) -> None:
    while True:
        await run_worker_once()
        await asyncio.sleep(sleep_seconds)
