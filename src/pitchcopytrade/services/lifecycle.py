from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.audit import AuditEvent
from pitchcopytrade.db.models.commerce import Payment, Subscription
from pitchcopytrade.db.models.enums import PaymentStatus, SubscriptionStatus
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore


@dataclass(slots=True)
class LifecycleStats:
    expired: int = 0
    cancelled: int = 0


async def expire_due_payments(
    session: AsyncSession | None,
    *,
    now: datetime | None = None,
    store: FileDataStore | None = None,
) -> LifecycleStats:
    timestamp = now or datetime.now(timezone.utc)
    if session is None:
        runtime_store = store or FileDataStore()
        graph = FileDatasetGraph.load(runtime_store)
        stats = LifecycleStats()
        for payment in graph.payments.values():
            if payment.status is not PaymentStatus.PENDING or payment.expires_at is None or payment.expires_at > timestamp:
                continue
            payment.status = PaymentStatus.EXPIRED
            stats.expired += 1
            for subscription in payment.subscriptions:
                if subscription.status is SubscriptionStatus.PENDING:
                    subscription.status = SubscriptionStatus.CANCELLED
                    stats.cancelled += 1
            graph.add(_build_lifecycle_event("payment.expired", payment.id, {"status": payment.status.value}))
        if stats.expired:
            graph.save(runtime_store)
        return stats

    query = (
        select(Payment)
        .options(selectinload(Payment.subscriptions))
        .where(Payment.status == PaymentStatus.PENDING)
    )
    result = await session.execute(query)
    stats = LifecycleStats()
    for payment in result.scalars().all():
        if payment.expires_at is None or payment.expires_at > timestamp:
            continue
        payment.status = PaymentStatus.EXPIRED
        stats.expired += 1
        for subscription in payment.subscriptions:
            if subscription.status is SubscriptionStatus.PENDING:
                subscription.status = SubscriptionStatus.CANCELLED
                stats.cancelled += 1
        session.add(_build_lifecycle_event("payment.expired", payment.id, {"status": payment.status.value}))
    if stats.expired:
        await session.commit()
    return stats


async def expire_due_subscriptions(
    session: AsyncSession | None,
    *,
    now: datetime | None = None,
    store: FileDataStore | None = None,
) -> LifecycleStats:
    timestamp = now or datetime.now(timezone.utc)
    expirable_statuses = {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL}
    if session is None:
        runtime_store = store or FileDataStore()
        graph = FileDatasetGraph.load(runtime_store)
        stats = LifecycleStats()
        for subscription in graph.subscriptions.values():
            if subscription.status not in expirable_statuses or subscription.end_at is None or subscription.end_at > timestamp:
                continue
            subscription.status = SubscriptionStatus.EXPIRED
            subscription.autorenew_enabled = False
            stats.expired += 1
            graph.add(
                _build_lifecycle_event(
                    "subscription.expired",
                    subscription.id,
                    {"status": subscription.status.value},
                )
            )
        if stats.expired:
            graph.save(runtime_store)
        return stats

    query = select(Subscription).where(Subscription.status.in_(expirable_statuses))
    result = await session.execute(query)
    stats = LifecycleStats()
    for subscription in result.scalars().all():
        if subscription.end_at is None or subscription.end_at > timestamp:
            continue
        subscription.status = SubscriptionStatus.EXPIRED
        subscription.autorenew_enabled = False
        stats.expired += 1
        session.add(
            _build_lifecycle_event(
                "subscription.expired",
                subscription.id,
                {"status": subscription.status.value},
            )
        )
    if stats.expired:
        await session.commit()
    return stats


def _build_lifecycle_event(action: str, entity_id: str, payload: dict[str, object]) -> AuditEvent:
    return AuditEvent(
        actor_user_id=None,
        entity_type=action.split(".")[0],
        entity_id=entity_id,
        action=action,
        payload=payload,
    )
