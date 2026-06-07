from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.db.models.audit import AuditEvent
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.enums import MessageStatus


async def publish_due_recommendations(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> list[Message]:
    current_time = now or datetime.now(timezone.utc)
    query = select(Message).where(
        Message.status == MessageStatus.SCHEDULED.value,
        Message.schedule.is_not(None),
        Message.schedule <= current_time,
    )
    result = await session.execute(query)
    recommendations = list(result.scalars().all())

    for item in recommendations:
        item.status = MessageStatus.PUBLISHED.value
        item.published = current_time
        item.schedule = None
        session.add(
            AuditEvent(
                actor_user_id=None,
                entity_type="message",
                entity_id=item.id,
                action="worker.scheduled_publish",
                payload={"status": item.status},
            )
        )

    if recommendations:
        await session.commit()
        for item in recommendations:
            await session.refresh(item)
    return recommendations
