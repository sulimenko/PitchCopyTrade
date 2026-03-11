from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import FastAPI


logger = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(app: FastAPI) -> AsyncIterator[None]:
    started_at = datetime.now(timezone.utc)
    app.state.started_at = started_at
    app.state.ready = True
    logger.info("API startup complete at %s", started_at.isoformat())

    try:
        yield
    finally:
        app.state.ready = False
        app.state.stopped_at = datetime.now(timezone.utc)
        logger.info("API shutdown complete")
