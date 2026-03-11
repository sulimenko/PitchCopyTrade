from __future__ import annotations

from fastapi import FastAPI

from pitchcopytrade import __version__
from pitchcopytrade.api.lifespan import app_lifespan
from pitchcopytrade.api.router import api_router
from pitchcopytrade.core.runtime import bootstrap_runtime


def create_app() -> FastAPI:
    settings = bootstrap_runtime("api")

    app = FastAPI(
        title=settings.app.name,
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=app_lifespan,
    )
    app.state.service_name = settings.app.name
    app.state.environment = settings.app.env
    app.state.base_timezone = settings.app.base_timezone
    app.state.storage_backend = "postgres+minio"
    app.state.payment_provider = settings.payments.provider
    app.state.ready = False
    app.include_router(api_router)
    return app


app = create_app()
