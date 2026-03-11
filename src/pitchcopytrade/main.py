from __future__ import annotations

from fastapi import FastAPI

from pitchcopytrade import __version__
from pitchcopytrade.api.router import api_router
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.core.logging import configure_logging

configure_logging()
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.include_router(api_router)
