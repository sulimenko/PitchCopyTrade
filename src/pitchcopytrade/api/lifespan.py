from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import FastAPI

from pitchcopytrade.core.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(app: FastAPI) -> AsyncIterator[None]:
    started_at = datetime.now(timezone.utc)
    app.state.started_at = started_at
    app.state.arq_pool = None

    settings = get_settings()

    if settings.app.data_mode == "db":
        await _run_seeders(settings)

    await _init_arq_pool(app, settings)

    app.state.ready = True
    logger.info("API startup complete at %s", started_at.isoformat())

    try:
        yield
    finally:
        app.state.ready = False
        if app.state.arq_pool is not None:
            try:
                await app.state.arq_pool.aclose()
            except Exception:
                pass
        app.state.stopped_at = datetime.now(timezone.utc)
        logger.info("API shutdown complete")


async def _run_seeders(settings) -> None:
    from pitchcopytrade.db.session import AsyncSessionLocal

    if AsyncSessionLocal is None:
        logger.warning("No DB session available, skipping seeders")
        return

    try:
        from pitchcopytrade.db.seeders.instruments import seed_instruments
        session = AsyncSessionLocal()
        try:
            count = await seed_instruments(session)
            if count:
                logger.info("Instruments seeded: %d", count)
        finally:
            try:
                await session.close()
            except ValueError as exc:
                if "greenlet" not in str(exc):
                    raise
    except Exception as exc:
        logger.error("Instrument seeder failed: %s", exc)

    try:
        from pitchcopytrade.db.seeders.admin import seed_admin
        session = AsyncSessionLocal()
        try:
            created = await seed_admin(
                session,
                telegram_id=settings.admin_telegram_id,
                email=settings.admin_email,
            )
            if created:
                logger.info("Admin user seeded")
        finally:
            try:
                await session.close()
            except ValueError as exc:
                if "greenlet" not in str(exc):
                    raise
    except Exception as exc:
        logger.error("Admin seeder failed: %s", exc)


async def _init_arq_pool(app: FastAPI, settings) -> None:
    del settings
    app.state.arq_pool = None
    logger.info("ARQ notification queue disabled: immediate publish uses direct delivery path")
