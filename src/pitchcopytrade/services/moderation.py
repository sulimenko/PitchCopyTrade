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


def _file_graph(store: FileDataStore | None = None) -> tuple[FileDatasetGraph, FileDataStore]:
    active_store = store or FileDataStore()
    return FileDatasetGraph.load(active_store), active_store


async def list_moderation_recommendations(
    session: AsyncSession | None,
    *,
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
        return items
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
    return list(result.scalars().all())


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
    if session is None:
        graph, _store = _file_graph(store)
        items = [item for item in graph.recommendations.values() if item.requires_moderation]
        return ModerationQueueStats(
            review_count=sum(1 for item in items if item.status == RecommendationStatus.REVIEW),
            scheduled_count=sum(1 for item in items if item.status == RecommendationStatus.SCHEDULED),
            published_count=sum(1 for item in items if item.status == RecommendationStatus.PUBLISHED),
        )
    review_count = await _count_query(
        session,
        select(func.count(Recommendation.id)).where(
            Recommendation.requires_moderation.is_(True),
            Recommendation.status == RecommendationStatus.REVIEW,
        ),
    )
    scheduled_count = await _count_query(
        session,
        select(func.count(Recommendation.id)).where(
            Recommendation.requires_moderation.is_(True),
            Recommendation.status == RecommendationStatus.SCHEDULED,
        ),
    )
    published_count = await _count_query(
        session,
        select(func.count(Recommendation.id)).where(
            Recommendation.requires_moderation.is_(True),
            Recommendation.status == RecommendationStatus.PUBLISHED,
        ),
    )
    return ModerationQueueStats(
        review_count=review_count,
        scheduled_count=scheduled_count,
        published_count=published_count,
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
