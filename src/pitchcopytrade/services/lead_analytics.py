from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.catalog import LeadSource
from pitchcopytrade.db.models.commerce import Subscription
from pitchcopytrade.db.models.enums import SubscriptionStatus
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore


ACTIVE_SUBSCRIPTION_STATUSES = {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL}


@dataclass(slots=True)
class LeadSourceAnalyticsRow:
    source_name: str
    source_type: str
    users_total: int
    subscriptions_total: int
    active_subscriptions: int
    payments_total: int
    paid_payments: int
    revenue_rub: int


async def list_lead_source_analytics(
    session: AsyncSession | None,
    *,
    store: FileDataStore | None = None,
) -> list[LeadSourceAnalyticsRow]:
    if session is None:
        runtime_store = store or FileDataStore()
        graph = FileDatasetGraph.load(runtime_store)
        return _build_file_rows(graph)

    sources_result = await session.execute(
        select(LeadSource)
        .options(
            selectinload(LeadSource.users),
            selectinload(LeadSource.subscriptions).selectinload(Subscription.payment),
        )
        .order_by(LeadSource.name.asc())
    )
    sources = list(sources_result.scalars().all())
    users_result = await session.execute(select(User))
    users = list(users_result.scalars().all())
    subscriptions_result = await session.execute(select(Subscription).options(selectinload(Subscription.payment)))
    subscriptions = list(subscriptions_result.scalars().all())
    return _build_rows(sources, users, subscriptions)


def _build_file_rows(graph: FileDatasetGraph) -> list[LeadSourceAnalyticsRow]:
    return _build_rows(
        list(graph.lead_sources.values()),
        list(graph.users.values()),
        list(graph.subscriptions.values()),
    )


def _build_rows(
    sources: list[LeadSource],
    users: list[User],
    subscriptions: list[Subscription],
) -> list[LeadSourceAnalyticsRow]:
    rows: list[LeadSourceAnalyticsRow] = []
    for source in sorted(sources, key=lambda item: item.name.lower()):
        rows.append(
            _row_from_entities(
                source_name=source.name,
                source_type=source.source_type.value,
                users=[item for item in users if item.lead_source_id == source.id],
                subscriptions=[item for item in subscriptions if item.lead_source_id == source.id],
            )
        )

    unattributed_users = [item for item in users if item.lead_source_id is None]
    unattributed_subscriptions = [item for item in subscriptions if item.lead_source_id is None]
    if unattributed_users or unattributed_subscriptions:
        rows.append(
            _row_from_entities(
                source_name="unattributed",
                source_type="unattributed",
                users=unattributed_users,
                subscriptions=unattributed_subscriptions,
            )
        )
    return rows


def _row_from_entities(
    *,
    source_name: str,
    source_type: str,
    users: list[User],
    subscriptions: list[Subscription],
) -> LeadSourceAnalyticsRow:
    payments_by_id = {
        item.payment.id: item.payment
        for item in subscriptions
        if item.payment is not None
    }
    paid_payments = [item for item in payments_by_id.values() if item.status.value == "paid"]
    return LeadSourceAnalyticsRow(
        source_name=source_name,
        source_type=source_type,
        users_total=len(users),
        subscriptions_total=len(subscriptions),
        active_subscriptions=sum(1 for item in subscriptions if item.status in ACTIVE_SUBSCRIPTION_STATUSES),
        payments_total=len(payments_by_id),
        paid_payments=len(paid_payments),
        revenue_rub=sum(item.final_amount_rub for item in paid_payments),
    )
