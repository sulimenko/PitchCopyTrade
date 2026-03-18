from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.db.models.catalog import Instrument
from pitchcopytrade.db.models.enums import InstrumentType

logger = logging.getLogger(__name__)

_STUB_PATH = Path(__file__).parents[5] / "doc" / "instruments_stub.json"


async def seed_instruments(session: AsyncSession) -> int:
    count_result = await session.execute(select(func.count(Instrument.id)))
    existing_count = int(count_result.scalar_one() or 0)
    if existing_count > 0:
        logger.info("Instruments already seeded (%d rows), skipping", existing_count)
        return 0

    data = json.loads(_STUB_PATH.read_text(encoding="utf-8"))
    instruments = data.get("instruments", [])

    seeded = 0
    for item in instruments:
        stmt = (
            insert(Instrument)
            .values(
                ticker=item["ticker"],
                name=item["name"],
                board=item["board"],
                lot_size=item["lot_size"],
                currency=item.get("currency", "RUB"),
                instrument_type=InstrumentType(item.get("instrument_type", "equity")),
                is_active=item.get("is_active", True),
            )
            .on_conflict_do_nothing(index_elements=["ticker"])
        )
        result = await session.execute(stmt)
        seeded += result.rowcount

    await session.commit()
    logger.info("Seeded %d instruments", seeded)
    return seeded
