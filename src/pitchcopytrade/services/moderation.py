from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.audit import AuditEvent
from pitchcopytrade.db.models.catalog import Strategy
from pitchcopytrade.db.models.content import Recommendation, RecommendationLeg
from pitchcopytrade.db.models.enums import RecommendationStatus
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore


@dataclass(slots=True)
class ModerationQueueStats:
    review_count: int
    scheduled_count: int
    published_count: int
    overdue_review_count: int = 0
    approved_total: int = 0
    rework_total: int = 0
    rejected_total: int = 0
    avg_resolution_hours: float | None = None


@dataclass(slots=True)
class ModerationDetailMetrics:
    first_submitted_at: datetime
    last_decision_at: datetime | None
    resolution_hours: float | None
    sla_state: str


def _file_graph(store: FileDataStore | None = None) -> tuple[FileDatasetGraph, FileDataStore]:
    active_store = store or FileDataStore()
    return FileDatasetGraph.load(active_store), active_store


async def list_moderation_recommendations(
    session: AsyncSession | None,
    *,
    status_filter: RecommendationStatus | None = None,
    query_text: str | None = None,
    store: FileDataStore | None = None,
) -> list[Recommendation]:
    if session is None:
        graph, _store = _file_graph(store)
        items = [
            item
            for item in graph.recommendations.values()
            if item.requires_moderation
            and item.status
            in {
                RecommendationStatus.REVIEW,
                RecommendationStatus.APPROVED,
                RecommendationStatus.SCHEDULED,
                RecommendationStatus.PUBLISHED,
            }
        ]
        items.sort(key=lambda item: (item.updated_at, item.created_at), reverse=True)
        return _filter_moderation_items(items, status_filter=status_filter, query_text=query_text)
    query = (
        select(Recommendation)
        .options(
            selectinload(Recommendation.strategy).selectinload(Strategy.author),
            selectinload(Recommendation.author).selectinload(AuthorProfile.user),
            selectinload(Recommendation.legs).selectinload(RecommendationLeg.instrument),
            selectinload(Recommendation.attachments),
        )
        .where(
            Recommendation.requires_moderation.is_(True),
            Recommendation.status.in_(
                [
                    RecommendationStatus.REVIEW,
                    RecommendationStatus.APPROVED,
                    RecommendationStatus.SCHEDULED,
                    RecommendationStatus.PUBLISHED,
                ]
            ),
        )
        .order_by(Recommendation.updated_at.desc(), Recommendation.created_at.desc())
    )
    result = await session.execute(query)
    return _filter_moderation_items(list(result.scalars().all()), status_filter=status_filter, query_text=query_text)


async def get_moderation_recommendation(
    session: AsyncSession | None,
    recommendation_id: str,
    *,
    store: FileDataStore | None = None,
) -> Recommendation | None:
    if session is None:
        graph, _store = _file_graph(store)
        return graph.recommendations.get(recommendation_id)
    query = (
        select(Recommendation)
        .options(
            selectinload(Recommendation.strategy).selectinload(Strategy.author),
            selectinload(Recommendation.author).selectinload(AuthorProfile.user),
            selectinload(Recommendation.legs).selectinload(RecommendationLeg.instrument),
            selectinload(Recommendation.attachments),
        )
        .where(Recommendation.id == recommendation_id)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def list_recommendation_audit_events(
    session: AsyncSession | None,
    recommendation_id: str,
    *,
    store: FileDataStore | None = None,
) -> list[AuditEvent]:
    if session is None:
        graph, _store = _file_graph(store)
        items = [
            item
            for item in graph.audit_events.values()
            if item.entity_type == "recommendation" and item.entity_id == recommendation_id
        ]
        items.sort(key=lambda item: item.created_at, reverse=True)
        return items
    query = (
        select(AuditEvent)
        .options(selectinload(AuditEvent.actor_user))
        .where(
            AuditEvent.entity_type == "recommendation",
            AuditEvent.entity_id == recommendation_id,
        )
        .order_by(AuditEvent.created_at.desc())
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_moderation_queue_stats(
    session: AsyncSession | None,
    *,
    store: FileDataStore | None = None,
) -> ModerationQueueStats:
    now = datetime.now(timezone.utc)
    if session is None:
        graph, _store = _file_graph(store)
        items = [item for item in graph.recommendations.values() if item.requires_moderation]
        events = [item for item in graph.audit_events.values() if item.entity_type == "recommendation"]
        return _build_queue_stats(items, events=events, now=now)
    recommendations_result = await session.execute(
        select(Recommendation).where(Recommendation.requires_moderation.is_(True))
    )
    recommendations = list(recommendations_result.scalars().all())
    events_result = await session.execute(
        select(AuditEvent).where(AuditEvent.entity_type == "recommendation")
    )
    events = list(events_result.scalars().all())
    return _build_queue_stats(recommendations, events=events, now=now)


def build_moderation_detail_metrics(
    recommendation: Recommendation,
    history: list[AuditEvent],
    *,
    now: datetime | None = None,
) -> ModerationDetailMetrics:
    timestamp = now or datetime.now(timezone.utc)
    first_submitted_at = recommendation.created_at or recommendation.updated_at or timestamp
    decision_events = [item for item in history if item.action in {"moderation.approve", "moderation.rework", "moderation.reject"}]
    last_decision_at = max((item.created_at for item in decision_events), default=None)
    resolution_hours = None
    if last_decision_at is not None:
        resolution_hours = round((last_decision_at - first_submitted_at).total_seconds() / 3600, 1)
    if recommendation.status == RecommendationStatus.REVIEW:
        sla_state = "overdue" if (timestamp - first_submitted_at).total_seconds() > 24 * 3600 else "within_sla"
    else:
        sla_state = "resolved"
    return ModerationDetailMetrics(
        first_submitted_at=first_submitted_at,
        last_decision_at=last_decision_at,
        resolution_hours=resolution_hours,
        sla_state=sla_state,
    )


async def approve_recommendation(
    session: AsyncSession | None,
    recommendation: Recommendation,
    moderator: User,
    comment: str | None = None,
    *,
    store: FileDataStore | None = None,
) -> Recommendation:
    now = datetime.now(timezone.utc)
    if session is None:
        graph, active_store = _file_graph(store)
        persisted = graph.recommendations.get(recommendation.id)
        if persisted is None:
            raise ValueError("Recommendation not found")
        persisted.moderated_by_user_id = moderator.id
        persisted.moderation_comment = (comment or "").strip() or None
        if persisted.scheduled_for and persisted.scheduled_for > now:
            persisted.status = RecommendationStatus.SCHEDULED
            persisted.published_at = None
        else:
            persisted.status = RecommendationStatus.PUBLISHED
            persisted.published_at = now
        graph.add(
            AuditEvent(
                actor_user_id=moderator.id,
                entity_type="recommendation",
                entity_id=persisted.id,
                action="moderation.approve",
                payload={"status": persisted.status.value, "comment": persisted.moderation_comment},
            )
        )
        graph.save(active_store)
        return persisted
    recommendation.moderated_by_user_id = moderator.id
    recommendation.moderation_comment = (comment or "").strip() or None
    if recommendation.scheduled_for and recommendation.scheduled_for > now:
        recommendation.status = RecommendationStatus.SCHEDULED
        recommendation.published_at = None
    else:
        recommendation.status = RecommendationStatus.PUBLISHED
        recommendation.published_at = now
    await _record_audit(
        session,
        actor_user_id=moderator.id,
        entity_id=recommendation.id,
        action="moderation.approve",
        payload={"status": recommendation.status.value, "comment": recommendation.moderation_comment},
    )
    await session.commit()
    await session.refresh(recommendation)
    return recommendation


async def send_recommendation_to_rework(
    session: AsyncSession | None,
    recommendation: Recommendation,
    moderator: User,
    comment: str,
    *,
    store: FileDataStore | None = None,
) -> Recommendation:
    if session is None:
        graph, active_store = _file_graph(store)
        persisted = graph.recommendations.get(recommendation.id)
        if persisted is None:
            raise ValueError("Recommendation not found")
        persisted.status = RecommendationStatus.DRAFT
        persisted.moderated_by_user_id = moderator.id
        persisted.moderation_comment = comment.strip() or "Нужна доработка"
        persisted.published_at = None
        graph.add(
            AuditEvent(
                actor_user_id=moderator.id,
                entity_type="recommendation",
                entity_id=persisted.id,
                action="moderation.rework",
                payload={"status": persisted.status.value, "comment": persisted.moderation_comment},
            )
        )
        graph.save(active_store)
        return persisted
    recommendation.status = RecommendationStatus.DRAFT
    recommendation.moderated_by_user_id = moderator.id
    recommendation.moderation_comment = comment.strip() or "Нужна доработка"
    recommendation.published_at = None
    await _record_audit(
        session,
        actor_user_id=moderator.id,
        entity_id=recommendation.id,
        action="moderation.rework",
        payload={"status": recommendation.status.value, "comment": recommendation.moderation_comment},
    )
    await session.commit()
    await session.refresh(recommendation)
    return recommendation


async def reject_recommendation(
    session: AsyncSession | None,
    recommendation: Recommendation,
    moderator: User,
    comment: str,
    *,
    store: FileDataStore | None = None,
) -> Recommendation:
    if session is None:
        graph, active_store = _file_graph(store)
        persisted = graph.recommendations.get(recommendation.id)
        if persisted is None:
            raise ValueError("Recommendation not found")
        persisted.status = RecommendationStatus.ARCHIVED
        persisted.moderated_by_user_id = moderator.id
        persisted.moderation_comment = comment.strip() or "Отклонено модератором"
        persisted.published_at = None
        graph.add(
            AuditEvent(
                actor_user_id=moderator.id,
                entity_type="recommendation",
                entity_id=persisted.id,
                action="moderation.reject",
                payload={"status": persisted.status.value, "comment": persisted.moderation_comment},
            )
        )
        graph.save(active_store)
        return persisted
    recommendation.status = RecommendationStatus.ARCHIVED
    recommendation.moderated_by_user_id = moderator.id
    recommendation.moderation_comment = comment.strip() or "Отклонено модератором"
    recommendation.published_at = None
    await _record_audit(
        session,
        actor_user_id=moderator.id,
        entity_id=recommendation.id,
        action="moderation.reject",
        payload={"status": recommendation.status.value, "comment": recommendation.moderation_comment},
    )
    await session.commit()
    await session.refresh(recommendation)
    return recommendation


async def _record_audit(
    session: AsyncSession,
    *,
    actor_user_id: str | None,
    entity_id: str,
    action: str,
    payload: dict | None,
) -> None:
    session.add(
        AuditEvent(
            actor_user_id=actor_user_id,
            entity_type="recommendation",
            entity_id=entity_id,
            action=action,
            payload=payload,
        )
    )
    await session.flush()


async def _count_query(session: AsyncSession, query) -> int:
    result = await session.execute(query)
    return int(result.scalar_one())


def _filter_moderation_items(
    items: list[Recommendation],
    *,
    status_filter: RecommendationStatus | None,
    query_text: str | None,
) -> list[Recommendation]:
    filtered = items
    if status_filter is not None:
        filtered = [item for item in filtered if item.status == status_filter]
    normalized = (query_text or "").strip().lower()
    if not normalized:
        return filtered
    return [item for item in filtered if _moderation_item_matches(item, normalized)]


def _moderation_item_matches(item: Recommendation, normalized: str) -> bool:
    parts = [
        item.title,
        item.summary,
        item.thesis,
        item.author.display_name if item.author is not None else None,
        item.strategy.title if item.strategy is not None else None,
        item.status.value,
        item.kind.value,
    ]
    haystack = " ".join(part.strip().lower() for part in parts if part)
    return normalized in haystack


def _build_queue_stats(
    recommendations: list[Recommendation],
    *,
    events: list[AuditEvent],
    now: datetime,
) -> ModerationQueueStats:
    resolution_hours: list[float] = []
    for recommendation in recommendations:
        detail = build_moderation_detail_metrics(
            recommendation,
            [item for item in events if item.entity_id == recommendation.id],
            now=now,
        )
        if detail.resolution_hours is not None:
            resolution_hours.append(detail.resolution_hours)

    return ModerationQueueStats(
        review_count=sum(1 for item in recommendations if item.status == RecommendationStatus.REVIEW),
        scheduled_count=sum(1 for item in recommendations if item.status == RecommendationStatus.SCHEDULED),
        published_count=sum(1 for item in recommendations if item.status == RecommendationStatus.PUBLISHED),
        overdue_review_count=sum(
            1
            for item in recommendations
            if item.status == RecommendationStatus.REVIEW and (now - item.created_at).total_seconds() > 24 * 3600
        ),
        approved_total=sum(1 for item in events if item.action == "moderation.approve"),
        rework_total=sum(1 for item in events if item.action == "moderation.rework"),
        rejected_total=sum(1 for item in events if item.action == "moderation.reject"),
        avg_resolution_hours=round(sum(resolution_hours) / len(resolution_hours), 1) if resolution_hours else None,
    )
