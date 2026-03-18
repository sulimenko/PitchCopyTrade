from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.models.catalog import Instrument
from pitchcopytrade.db.session import get_optional_db_session
from pitchcopytrade.repositories.author import FileAuthorRepository

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/instruments")
async def get_instruments(
    q: str | None = None,
    session: AsyncSession | None = Depends(get_optional_db_session),
):
    if get_settings().app.data_mode == "file":
        repo = FileAuthorRepository()
        instruments = await repo.list_active_instruments()
        if q:
            q_lower = q.lower()
            instruments = [i for i in instruments if q_lower in i.ticker.lower() or q_lower in i.name.lower()]
        return [_instrument_dict(i) for i in instruments]

    if session is None:
        return []

    query = select(Instrument).where(Instrument.is_active.is_(True))
    if q:
        from sqlalchemy import func
        q_like = f"%{q.lower()}%"
        query = query.where(
            func.lower(Instrument.ticker).like(q_like) | func.lower(Instrument.name).like(q_like)
        )
    query = query.order_by(Instrument.ticker.asc())
    result = await session.execute(query)
    instruments = result.scalars().all()

    return [_instrument_dict(i) for i in instruments]


def _instrument_dict(i) -> dict:
    return {
        "ticker": i.ticker,
        "name": i.name,
        "board": i.board,
        "currency": i.currency,
        "is_active": i.is_active,
        "last_price": None,
        "change_pct": None,
    }
