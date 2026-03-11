from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pitchcopytrade.worker.jobs.placeholders import WORKER_JOBS, WorkerJob, run_scheduled_publish
from pitchcopytrade.worker.runner import DEFAULT_WORKER_SLEEP_SECONDS, get_worker_jobs, run_worker_loop, run_worker_once


def test_worker_jobs_registry_contains_required_jobs() -> None:
    names = [job.name for job in get_worker_jobs()]

    assert names == [
        "scheduled_publish",
        "payment_expiry_sync",
        "subscription_expiry",
        "reminder_jobs",
    ]
    assert all(isinstance(job, WorkerJob) for job in WORKER_JOBS)


@pytest.mark.asyncio
async def test_run_worker_once_executes_all_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    executed: list[str] = []

    def build_job(name: str) -> WorkerJob:
        async def runner() -> None:
            executed.append(name)

        return WorkerJob(name=name, runner=runner)

    fake_jobs = tuple(build_job(job.name) for job in WORKER_JOBS)
    monkeypatch.setattr("pitchcopytrade.worker.runner.WORKER_JOBS", fake_jobs)

    await run_worker_once()

    assert executed == [job.name for job in fake_jobs]


@pytest.mark.asyncio
async def test_run_worker_loop_sleeps_between_ticks(monkeypatch: pytest.MonkeyPatch) -> None:
    once = AsyncMock()
    sleep = AsyncMock(side_effect=RuntimeError("stop-loop"))
    monkeypatch.setattr("pitchcopytrade.worker.runner.run_worker_once", once)
    monkeypatch.setattr("pitchcopytrade.worker.runner.asyncio.sleep", sleep)

    with pytest.raises(RuntimeError, match="stop-loop"):
        await run_worker_loop()

    once.assert_awaited_once()
    sleep.assert_awaited_once_with(DEFAULT_WORKER_SLEEP_SECONDS)


@pytest.mark.asyncio
async def test_run_scheduled_publish_delivers_notifications(monkeypatch: pytest.MonkeyPatch) -> None:
    recommendation = object()
    fake_bot = AsyncMock()

    class DummySessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("pitchcopytrade.worker.jobs.placeholders.AsyncSessionLocal", lambda: DummySessionContext())
    monkeypatch.setattr(
        "pitchcopytrade.worker.jobs.placeholders.publish_due_recommendations",
        lambda _session: _async_return([recommendation]),
    )
    monkeypatch.setattr("pitchcopytrade.worker.jobs.placeholders.create_bot", lambda _token: fake_bot)
    notifier = AsyncMock()
    monkeypatch.setattr(
        "pitchcopytrade.worker.jobs.placeholders.deliver_recommendation_notifications",
        notifier,
    )

    await run_scheduled_publish()

    notifier.assert_awaited_once()
    fake_bot.session.close.assert_awaited_once()


async def _async_return(value):
    return value
