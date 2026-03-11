from __future__ import annotations

from fastapi import APIRouter

from pitchcopytrade import __version__
from pitchcopytrade.core.config import get_settings

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "service": settings.app.name, "env": settings.app.env}


@router.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}


@router.get("/meta")
async def meta() -> dict[str, str]:
    settings = get_settings()
    return {
        "service": settings.app.name,
        "version": __version__,
        "timezone": settings.app.base_timezone,
        "storage": "postgres+minio",
        "payments": settings.payments.provider,
    }
