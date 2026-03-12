from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.accounts import AuthorProfile
from pitchcopytrade.db.models.audit import AuditEvent
from pitchcopytrade.db.models.catalog import Strategy
from pitchcopytrade.db.models.content import Recommendation, RecommendationLeg
from pitchcopytrade.db.models.enums import RecommendationStatus
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore
from pitchcopytrade.services.notifications import (
    deliver_recommendation_notifications,
    deliver_recommendation_notifications_file,
)


DELIVERY_ACTIONS = {"notification.delivery", "worker.scheduled_publish"}


@dataclass(slots=True)
class DeliveryRecord:
    recommendation: Recommendation
    events: list[AuditEvent]
    latest_delivery_event: AuditEvent | None
    delivery_attempts: int
    delivered_recipients: int


def _file_delivery_graph(store: FileDataStore | None = None) -> tuple[FileDatasetGraph, FileDataStore]:
    runtime_store = store or FileDataStore()
    graph = FileDatasetGraph.load(runtime_store)
    return graph, runtime_store


async def list_admin_delivery_records(
    session: AsyncSession | None,
    *,
    store: FileDataStore | None = None,
) -> list[DeliveryRecord]:
    if session is None:
        graph, _store = _file_delivery_graph(store)
        recommendations = sorted(
            [item for item in graph.recommendations.values() if item.published_at is not None],
            key=lambda item: (item.published_at, item.updated_at),
            reverse=True,
        )
        return [_build_delivery_record(item, _events_for_recommendation(graph.audit_events.values(), item.id)) for item in recommendations]

    recommendations = await _list_published_recommendations(session)
    events = await _list_delivery_events(session)
    return [_build_delivery_record(item, _events_for_recommendation(events, item.id)) for item in recommendations]


async def get_admin_delivery_record(
    session: AsyncSession | None,
    recommendation_id: str,
    *,
    store: FileDataStore | None = None,
) -> DeliveryRecord | None:
    if session is None:
        graph, _store = _file_delivery_graph(store)
        recommendation = graph.recommendations.get(recommendation_id)
        if recommendation is None:
            return None
        return _build_delivery_record(recommendation, _events_for_recommendation(graph.audit_events.values(), recommendation.id))

    recommendation = await _get_published_recommendation(session, recommendation_id)
    if recommendation is None:
        return None
    events = await _list_delivery_events(session)
    return _build_delivery_record(recommendation, _events_for_recommendation(events, recommendation.id))


async def retry_recommendation_delivery(
    session: AsyncSession | None,
    recommendation_id: str,
    notifier,
    *,
    store: FileDataStore | None = None,
) -> DeliveryRecord:
    if session is None:
        graph, runtime_store = _file_delivery_graph(store)
        recommendation = graph.recommendations.get(recommendation_id)
        if recommendation is None:
            raise ValueError("Recommendation not found")
        if recommendation.published_at is None:
            raise ValueError("Повторно отправлять можно только опубликованную рекомендацию")
        await deliver_recommendation_notifications_file(
            graph,
            runtime_store,
            recommendation,
            notifier,
            trigger="manual_retry",
        )
        return _build_delivery_record(recommendation, _events_for_recommendation(graph.audit_events.values(), recommendation.id))

    recommendation = await _get_published_recommendation(session, recommendation_id)
    if recommendation is None:
        raise ValueError("Recommendation not found")
    if recommendation.published_at is None:
        raise ValueError("Повторно отправлять можно только опубликованную рекомендацию")
    await deliver_recommendation_notifications(session, recommendation, notifier, trigger="manual_retry")
    events = await _list_delivery_events(session)
    return _build_delivery_record(recommendation, _events_for_recommendation(events, recommendation.id))


def _build_delivery_record(recommendation: Recommendation, events: list[AuditEvent]) -> DeliveryRecord:
    delivery_events = [item for item in events if item.action == "notification.delivery"]
    latest_delivery_event = delivery_events[0] if delivery_events else None
    delivered_recipients = sum(int((item.payload or {}).get("recipient_count", 0)) for item in delivery_events)
    return DeliveryRecord(
        recommendation=recommendation,
        events=events,
        latest_delivery_event=latest_delivery_event,
        delivery_attempts=len(delivery_events),
        delivered_recipients=delivered_recipients,
    )


def _events_for_recommendation(events, recommendation_id: str) -> list[AuditEvent]:
    return sorted(
        [
            item
            for item in events
            if item.entity_type == "recommendation"
            and item.entity_id == recommendation_id
            and item.action in DELIVERY_ACTIONS
        ],
        key=lambda item: item.created_at,
        reverse=True,
    )


async def _list_published_recommendations(session: AsyncSession) -> list[Recommendation]:
    query = (
        select(Recommendation)
        .options(
            selectinload(Recommendation.strategy).selectinload(Strategy.author).selectinload(AuthorProfile.user),
            selectinload(Recommendation.author).selectinload(AuthorProfile.user),
            selectinload(Recommendation.legs).selectinload(RecommendationLeg.instrument),
            selectinload(Recommendation.attachments),
        )
        .where(
            Recommendation.status.in_([RecommendationStatus.PUBLISHED, RecommendationStatus.CLOSED]),
            Recommendation.published_at.is_not(None),
        )
        .order_by(Recommendation.published_at.desc(), Recommendation.updated_at.desc())
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def _get_published_recommendation(session: AsyncSession, recommendation_id: str) -> Recommendation | None:
    query = (
        select(Recommendation)
        .options(
            selectinload(Recommendation.strategy).selectinload(Strategy.author).selectinload(AuthorProfile.user),
            selectinload(Recommendation.author).selectinload(AuthorProfile.user),
            selectinload(Recommendation.legs).selectinload(RecommendationLeg.instrument),
            selectinload(Recommendation.attachments),
        )
        .where(Recommendation.id == recommendation_id)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def _list_delivery_events(session: AsyncSession) -> list[AuditEvent]:
    query = (
        select(AuditEvent)
        .options(selectinload(AuditEvent.actor_user))
        .where(
            AuditEvent.entity_type == "recommendation",
            AuditEvent.action.in_(DELIVERY_ACTIONS),
        )
        .order_by(AuditEvent.created_at.desc())
    )
    result = await session.execute(query)
    return list(result.scalars().all())
