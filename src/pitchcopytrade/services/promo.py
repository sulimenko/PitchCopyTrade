from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.db.models.commerce import Payment, PromoCode
from pitchcopytrade.db.models.enums import PaymentStatus
from pitchcopytrade.db.models.commerce import Subscription
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore


@dataclass(slots=True)
class PromoApplication:
    promo_code: PromoCode
    discount_rub: int
    final_amount_rub: int


def apply_promo_to_amount(
    promo_code: PromoCode,
    *,
    amount_rub: int,
) -> PromoApplication:
    discount_rub = 0
    if promo_code.discount_percent is not None:
        discount_rub = (amount_rub * promo_code.discount_percent) // 100
    elif promo_code.discount_amount_rub is not None:
        discount_rub = promo_code.discount_amount_rub
    discount_rub = max(0, min(amount_rub, discount_rub))
    return PromoApplication(
        promo_code=promo_code,
        discount_rub=discount_rub,
        final_amount_rub=max(0, amount_rub - discount_rub),
    )


def validate_promo_code_for_checkout(
    promo_code: PromoCode,
    *,
    paid_redemptions: int,
    now: datetime | None = None,
) -> None:
    timestamp = now or datetime.now(timezone.utc)
    if not promo_code.is_active:
        raise ValueError("Промокод неактивен")
    if promo_code.expires_at is not None and promo_code.expires_at <= timestamp:
        raise ValueError("Срок действия промокода истек")
    if promo_code.max_redemptions is not None and paid_redemptions >= promo_code.max_redemptions:
        raise ValueError("Лимит использований промокода исчерпан")


async def sync_promo_redemption_counter(
    session: AsyncSession | None,
    promo_code: PromoCode | None,
    *,
    store: FileDataStore | None = None,
) -> None:
    if promo_code is None:
        return
    if session is None:
        runtime_store = store or FileDataStore()
        graph = FileDatasetGraph.load(runtime_store)
        persisted = graph.promo_codes.get(promo_code.id)
        if persisted is None:
            return
        persisted.current_redemptions = count_redemptions_file(graph, persisted)
        graph.save(runtime_store)
        promo_code.current_redemptions = persisted.current_redemptions
        return

    result = await session.execute(
        select(func.count(Subscription.id)).where(
            Subscription.applied_promo_code_id == promo_code.id,
        )
    )
    promo_code.current_redemptions = int(result.scalar_one() or 0)
    await session.commit()
    await session.refresh(promo_code)


def count_redemptions_file(graph: FileDatasetGraph, promo_code: PromoCode) -> int:
    return sum(
        1
        for subscription in graph.subscriptions.values()
        if subscription.applied_promo_code_id == promo_code.id
    )
