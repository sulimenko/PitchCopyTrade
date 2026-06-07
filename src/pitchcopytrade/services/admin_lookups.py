from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.db.models.catalog import Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import PromoCode
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore


def _file_admin_graph(store: FileDataStore | None = None) -> tuple[FileDatasetGraph, FileDataStore]:
    runtime_store = store or FileDataStore()
    graph = FileDatasetGraph.load(runtime_store)
    return graph, runtime_store


async def get_strategy_by_slug(session: AsyncSession | None, slug: str) -> Strategy | None:
    if session is None:
        graph, _store = _file_admin_graph()
        return next((item for item in graph.strategies.values() if item.slug == slug), None)
    result = await session.execute(select(Strategy).where(Strategy.slug == slug))
    return result.scalar_one_or_none()


async def get_product_by_slug(session: AsyncSession | None, slug: str) -> SubscriptionProduct | None:
    if session is None:
        graph, _store = _file_admin_graph()
        return next((item for item in graph.products.values() if item.slug == slug), None)
    result = await session.execute(select(SubscriptionProduct).where(SubscriptionProduct.slug == slug))
    return result.scalar_one_or_none()


async def get_promo_code_by_code(session: AsyncSession | None, code: str) -> PromoCode | None:
    if session is None:
        graph, _store = _file_admin_graph()
        return next((item for item in graph.promo_codes.values() if item.code == code), None)
    result = await session.execute(select(PromoCode).where(PromoCode.code == code))
    return result.scalar_one_or_none()
