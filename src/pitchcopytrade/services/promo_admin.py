from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.db.models.commerce import PromoCode
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore


@dataclass(slots=True)
class PromoCodeFormData:
    code: str
    description: str | None
    discount_percent: int | None
    discount_amount_rub: int | None
    max_redemptions: int | None
    expires_at: datetime | None
    is_active: bool


def _file_promo_graph(store: FileDataStore | None = None) -> tuple[FileDatasetGraph, FileDataStore]:
    runtime_store = store or FileDataStore()
    graph = FileDatasetGraph.load(runtime_store)
    return graph, runtime_store


async def list_admin_promo_codes(
    session: AsyncSession | None,
    *,
    store: FileDataStore | None = None,
) -> list[PromoCode]:
    if session is None:
        graph, _runtime_store = _file_promo_graph(store)
        items = list(graph.promo_codes.values())
        items.sort(key=lambda item: (item.is_active, item.created_at, item.code), reverse=True)
        return items
    query = select(PromoCode).order_by(PromoCode.is_active.desc(), PromoCode.created_at.desc(), PromoCode.code.asc())
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_admin_promo_code(
    session: AsyncSession | None,
    promo_code_id: str,
    *,
    store: FileDataStore | None = None,
) -> PromoCode | None:
    if session is None:
        graph, _runtime_store = _file_promo_graph(store)
        return graph.promo_codes.get(promo_code_id)
    result = await session.execute(select(PromoCode).where(PromoCode.id == promo_code_id))
    return result.scalar_one_or_none()


async def create_admin_promo_code(
    session: AsyncSession | None,
    data: PromoCodeFormData,
    *,
    store: FileDataStore | None = None,
) -> PromoCode:
    promo = PromoCode(
        code=data.code,
        description=data.description,
        discount_percent=data.discount_percent,
        discount_amount_rub=data.discount_amount_rub,
        max_redemptions=data.max_redemptions,
        current_redemptions=0,
        expires_at=data.expires_at,
        is_active=data.is_active,
    )
    if session is None:
        graph, runtime_store = _file_promo_graph(store)
        _ensure_promo_code_is_unique(graph.promo_codes.values(), promo)
        graph.add(promo)
        graph.save(runtime_store)
        return graph.promo_codes[promo.id]

    existing = await _find_same_code(session, data.code)
    if existing is not None:
        raise ValueError("Промокод с таким кодом уже существует")
    session.add(promo)
    await session.commit()
    await session.refresh(promo)
    return promo


async def update_admin_promo_code(
    session: AsyncSession | None,
    promo: PromoCode,
    data: PromoCodeFormData,
    *,
    store: FileDataStore | None = None,
) -> PromoCode:
    promo.code = data.code
    promo.description = data.description
    promo.discount_percent = data.discount_percent
    promo.discount_amount_rub = data.discount_amount_rub
    promo.max_redemptions = data.max_redemptions
    promo.expires_at = data.expires_at
    promo.is_active = data.is_active

    if session is None:
        graph, runtime_store = _file_promo_graph(store)
        persisted = graph.promo_codes.get(promo.id)
        if persisted is None:
            raise ValueError("Promo code not found")
        _ensure_promo_code_is_unique([item for item in graph.promo_codes.values() if item.id != promo.id], promo)
        persisted.code = promo.code
        persisted.description = promo.description
        persisted.discount_percent = promo.discount_percent
        persisted.discount_amount_rub = promo.discount_amount_rub
        persisted.max_redemptions = promo.max_redemptions
        persisted.expires_at = promo.expires_at
        persisted.is_active = promo.is_active
        graph.save(runtime_store)
        return persisted

    existing = await _find_same_code(session, data.code)
    if existing is not None and existing.id != promo.id:
        raise ValueError("Промокод с таким кодом уже существует")
    await session.commit()
    await session.refresh(promo)
    return promo


def _ensure_promo_code_is_unique(items, target: PromoCode) -> None:
    for item in items:
        if item.code.upper() == target.code.upper():
            raise ValueError("Промокод с таким кодом уже существует")


async def _find_same_code(session: AsyncSession, code: str) -> PromoCode | None:
    result = await session.execute(select(PromoCode).where(PromoCode.code == code))
    return result.scalar_one_or_none()
