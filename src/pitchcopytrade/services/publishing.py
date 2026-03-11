from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.db.models.audit import AuditEvent
from pitchcopytrade.db.models.content import Recommendation
from pitchcopytrade.db.models.enums import RecommendationStatus


async def publish_due_recommendations(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> list[Recommendation]:
    current_time = now or datetime.now(timezone.utc)
    query = select(Recommendation).where(
        Recommendation.status == RecommendationStatus.SCHEDULED,
        Recommendation.scheduled_for.is_not(None),
        Recommendation.scheduled_for <= current_time,
    )
    result = await session.execute(query)
    recommendations = list(result.scalars().all())

    for item in recommendations:
        item.status = RecommendationStatus.PUBLISHED
        item.published_at = current_time
        item.scheduled_for = None
        session.add(
            AuditEvent(
                actor_user_id=None,
                entity_type="recommendation",
                entity_id=item.id,
                action="worker.scheduled_publish",
                payload={"status": item.status.value},
            )
        )

    if recommendations:
        await session.commit()
        for item in recommendations:
            await session.refresh(item)
    return recommendations
