from __future__ import annotations

from arq.connections import RedisSettings

from pitchcopytrade.core.config import get_settings
from pitchcopytrade.worker.jobs.notifications import send_recommendation_notifications


class WorkerSettings:
    functions = [send_recommendation_notifications]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 10
    job_timeout = 60
    retry_jobs = True
    max_tries = 3
