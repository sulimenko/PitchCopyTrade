from __future__ import annotations

from fastapi import FastAPI

from pitchcopytrade import __version__
from pitchcopytrade.api.router import api_router
from pitchcopytrade.core.runtime import bootstrap_runtime


def create_app() -> FastAPI:
    settings = bootstrap_runtime("api")

    app = FastAPI(
        title=settings.app.name,
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.include_router(api_router)
    return app


app = create_app()
