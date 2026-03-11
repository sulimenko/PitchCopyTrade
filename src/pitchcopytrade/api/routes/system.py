from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from fastapi import Request

from pitchcopytrade import __version__
from pitchcopytrade.core.config import get_settings

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(request: Request) -> dict[str, str]:
    return {
        "status": "ok",
        "service": request.app.state.service_name,
        "env": request.app.state.environment,
    }


@router.get("/ready")
async def ready(request: Request) -> dict[str, str]:
    return {
        "status": "ready" if request.app.state.ready else "starting",
        "service": request.app.state.service_name,
    }


@router.get("/meta")
@router.get("/metadata")
async def meta(request: Request) -> dict[str, str]:
    return {
        "service": request.app.state.service_name,
        "version": __version__,
        "env": request.app.state.environment,
        "timezone": request.app.state.base_timezone,
        "storage": request.app.state.storage_backend,
        "payments": request.app.state.payment_provider,
        "started_at": _serialize_datetime(getattr(request.app.state, "started_at", None)),
    }


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
