from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pitchcopytrade.worker.jobs.placeholders import (
    WORKER_JOBS,
    WorkerJob,
    run_payment_expiry_sync,
    run_reminder_jobs,
    run_scheduled_publish,
)
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

    results = await run_worker_once()

    assert executed == [job.name for job in fake_jobs]
    assert all(result.ok for result in results)


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


@pytest.mark.asyncio
async def test_run_payment_expiry_sync_uses_tbank_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    sync_mock = AsyncMock(return_value=type("Stats", (), {"checked": 1, "paid": 1, "failed": 0, "pending": 0})())
    monkeypatch.setattr(
        "pitchcopytrade.worker.jobs.placeholders.get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "payments": type(
                    "Payments",
                    (),
                    {
                        "provider": "tbank",
                        "tinkoff_terminal_key": type("Secret", (), {"get_secret_value": lambda self: "term"})(),
                        "tinkoff_secret_key": type("Secret", (), {"get_secret_value": lambda self: "secret"})(),
                    },
                )(),
            },
        )(),
    )
    monkeypatch.setattr("pitchcopytrade.worker.jobs.placeholders.AsyncSessionLocal", None)
    monkeypatch.setattr("pitchcopytrade.worker.jobs.placeholders.sync_tbank_pending_payments", sync_mock)

    await run_payment_expiry_sync()

    sync_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_reminder_jobs_uses_delivery_service(monkeypatch: pytest.MonkeyPatch) -> None:
    reminder_mock = AsyncMock(return_value=type("Stats", (), {"sent": 2, "skipped": 1})())
    fake_bot = AsyncMock()
    monkeypatch.setattr("pitchcopytrade.worker.jobs.placeholders.AsyncSessionLocal", None)
    monkeypatch.setattr("pitchcopytrade.worker.jobs.placeholders.create_bot", lambda _token: fake_bot)
    monkeypatch.setattr(
        "pitchcopytrade.worker.jobs.placeholders.get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "telegram": type(
                    "Telegram",
                    (),
                    {"bot_token": type("Secret", (), {"get_secret_value": lambda self: "token"})()},
                )(),
            },
        )(),
    )
    monkeypatch.setattr("pitchcopytrade.worker.jobs.placeholders.deliver_subscriber_reminders", reminder_mock)

    await run_reminder_jobs()

    reminder_mock.assert_awaited_once()
    fake_bot.session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_worker_once_continues_after_job_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    executed: list[str] = []

    async def failing() -> None:
        executed.append("first")
        raise RuntimeError("boom")

    async def succeeding() -> None:
        executed.append("second")

    monkeypatch.setattr(
        "pitchcopytrade.worker.runner.WORKER_JOBS",
        (
            WorkerJob(name="failing", runner=failing),
            WorkerJob(name="succeeding", runner=succeeding),
        ),
    )

    results = await run_worker_once()

    assert executed == ["first", "second"]
    assert results[0].ok is False
    assert results[1].ok is True


async def _async_return(value):
    return value
