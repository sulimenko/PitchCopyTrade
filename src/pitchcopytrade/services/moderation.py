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


@dataclass(slots=True)
class ModerationQueueStats:
    review_count: int
    scheduled_count: int
    published_count: int


async def list_moderation_recommendations(session: AsyncSession) -> list[Recommendation]:
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


async def get_moderation_recommendation(session: AsyncSession, recommendation_id: str) -> Recommendation | None:
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


async def list_recommendation_audit_events(session: AsyncSession, recommendation_id: str) -> list[AuditEvent]:
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


async def get_moderation_queue_stats(session: AsyncSession) -> ModerationQueueStats:
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
    session: AsyncSession,
    recommendation: Recommendation,
    moderator: User,
    comment: str | None = None,
) -> Recommendation:
    now = datetime.now(timezone.utc)
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
    session: AsyncSession,
    recommendation: Recommendation,
    moderator: User,
    comment: str,
) -> Recommendation:
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
    session: AsyncSession,
    recommendation: Recommendation,
    moderator: User,
    comment: str,
) -> Recommendation:
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
