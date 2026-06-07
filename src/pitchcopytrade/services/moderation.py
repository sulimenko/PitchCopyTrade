from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.audit import AuditEvent
from pitchcopytrade.db.models.catalog import Strategy
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.enums import MessageModeration, MessageStatus
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
    status_filter: MessageStatus | None = None,
    query_text: str | None = None,
    store: FileDataStore | None = None,
) -> list[Message]:
    if session is None:
        graph, _store = _file_graph(store)
        items = [
            item
            for item in graph.messages.values()
            if item.moderation == MessageModeration.REQUIRED.value
            and item.status
            in {
                MessageStatus.REVIEW.value,
                MessageStatus.APPROVED.value,
                MessageStatus.SCHEDULED.value,
                MessageStatus.PUBLISHED.value,
            }
        ]
        items.sort(key=lambda item: (item.updated, item.created), reverse=True)
        return _filter_moderation_items(items, status_filter=status_filter, query_text=query_text)
    query = (
        select(Message)
        .options(
            selectinload(Message.strategy).selectinload(Strategy.author),
            selectinload(Message.author).selectinload(AuthorProfile.user),
            selectinload(Message.user),
            selectinload(Message.moderator),
        )
        .where(
            Message.moderation == MessageModeration.REQUIRED.value,
            Message.status.in_(
                [
                    MessageStatus.REVIEW.value,
                    MessageStatus.APPROVED.value,
                    MessageStatus.SCHEDULED.value,
                    MessageStatus.PUBLISHED.value,
                ]
            ),
        )
        .order_by(Message.updated.desc(), Message.created.desc())
    )
    result = await session.execute(query)
    return _filter_moderation_items(list(result.scalars().all()), status_filter=status_filter, query_text=query_text)


async def get_moderation_message(
    session: AsyncSession | None,
    recommendation_id: str,
    *,
    store: FileDataStore | None = None,
) -> Message | None:
    if session is None:
        graph, _store = _file_graph(store)
        return graph.messages.get(recommendation_id)
    query = (
        select(Message)
        .options(
            selectinload(Message.strategy).selectinload(Strategy.author),
            selectinload(Message.author).selectinload(AuthorProfile.user),
            selectinload(Message.user),
            selectinload(Message.moderator),
        )
        .where(Message.id == recommendation_id)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def list_message_audit_events(
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
            if item.entity_type == "message" and item.entity_id == recommendation_id
        ]
        items.sort(key=lambda item: item.created_at, reverse=True)
        return items
    query = (
        select(AuditEvent)
        .options(selectinload(AuditEvent.actor_user))
        .where(
            AuditEvent.entity_type == "message",
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
        items = [item for item in graph.messages.values() if item.moderation == MessageModeration.REQUIRED.value]
        events = [item for item in graph.audit_events.values() if item.entity_type == "message"]
        return _build_queue_stats(items, events=events, now=now)
    recommendations_result = await session.execute(select(Message).where(Message.moderation == MessageModeration.REQUIRED.value))
    recommendations = list(recommendations_result.scalars().all())
    events_result = await session.execute(select(AuditEvent).where(AuditEvent.entity_type == "message"))
    events = list(events_result.scalars().all())
    return _build_queue_stats(recommendations, events=events, now=now)


def build_moderation_detail_metrics(
    recommendation: Message,
    history: list[AuditEvent],
    *,
    now: datetime | None = None,
) -> ModerationDetailMetrics:
    timestamp = now or datetime.now(timezone.utc)
    first_submitted_at = recommendation.created or recommendation.updated or timestamp
    decision_events = [item for item in history if item.action in {"moderation.approve", "moderation.rework", "moderation.reject"}]
    last_decision_at = max((item.created_at for item in decision_events), default=None)
    resolution_hours = None
    if last_decision_at is not None:
        resolution_hours = round((last_decision_at - first_submitted_at).total_seconds() / 3600, 1)
    if recommendation.status == MessageStatus.REVIEW.value:
        sla_state = "overdue" if (timestamp - first_submitted_at).total_seconds() > 24 * 3600 else "within_sla"
    else:
        sla_state = "resolved"
    return ModerationDetailMetrics(
        first_submitted_at=first_submitted_at,
        last_decision_at=last_decision_at,
        resolution_hours=resolution_hours,
        sla_state=sla_state,
    )


async def approve_message(
    session: AsyncSession | None,
    recommendation: Message,
    moderator: User,
    comment: str | None = None,
    *,
    store: FileDataStore | None = None,
) -> Message:
    now = datetime.now(timezone.utc)
    if session is None:
        graph, active_store = _file_graph(store)
        persisted = graph.messages.get(recommendation.id)
        if persisted is None:
            raise ValueError("Message not found")
        persisted.moderator_id = moderator.id
        persisted.comment = (comment or "").strip() or None
        if persisted.schedule and persisted.schedule > now:
            persisted.status = MessageStatus.SCHEDULED.value
            persisted.published = None
        else:
            persisted.status = MessageStatus.PUBLISHED.value
            persisted.published = now
        graph.add(
            AuditEvent(
                actor_user_id=moderator.id,
                entity_type="message",
                entity_id=persisted.id,
                action="moderation.approve",
                payload={"status": persisted.status, "comment": persisted.comment},
            )
        )
        graph.save(active_store)
        return persisted
    recommendation.moderator_id = moderator.id
    recommendation.comment = (comment or "").strip() or None
    if recommendation.schedule and recommendation.schedule > now:
        recommendation.status = MessageStatus.SCHEDULED.value
        recommendation.published = None
    else:
        recommendation.status = MessageStatus.PUBLISHED.value
        recommendation.published = now
    await _record_audit(
        session,
        actor_user_id=moderator.id,
        entity_id=recommendation.id,
        action="moderation.approve",
        payload={"status": recommendation.status, "comment": recommendation.comment},
    )
    await session.commit()
    await session.refresh(recommendation)
    return recommendation


async def send_message_to_rework(
    session: AsyncSession | None,
    recommendation: Message,
    moderator: User,
    comment: str,
    *,
    store: FileDataStore | None = None,
) -> Message:
    if session is None:
        graph, active_store = _file_graph(store)
        persisted = graph.messages.get(recommendation.id)
        if persisted is None:
            raise ValueError("Message not found")
        persisted.status = MessageStatus.DRAFT.value
        persisted.moderator_id = moderator.id
        persisted.comment = comment.strip() or "Нужна доработка"
        persisted.published = None
        graph.add(
            AuditEvent(
                actor_user_id=moderator.id,
                entity_type="message",
                entity_id=persisted.id,
                action="moderation.rework",
                payload={"status": persisted.status, "comment": persisted.comment},
            )
        )
        graph.save(active_store)
        return persisted
    recommendation.status = MessageStatus.DRAFT.value
    recommendation.moderator_id = moderator.id
    recommendation.comment = comment.strip() or "Нужна доработка"
    recommendation.published = None
    await _record_audit(
        session,
        actor_user_id=moderator.id,
        entity_id=recommendation.id,
        action="moderation.rework",
        payload={"status": recommendation.status, "comment": recommendation.comment},
    )
    await session.commit()
    await session.refresh(recommendation)
    return recommendation


async def reject_message(
    session: AsyncSession | None,
    recommendation: Message,
    moderator: User,
    comment: str,
    *,
    store: FileDataStore | None = None,
) -> Message:
    if session is None:
        graph, active_store = _file_graph(store)
        persisted = graph.messages.get(recommendation.id)
        if persisted is None:
            raise ValueError("Message not found")
        persisted.status = MessageStatus.ARCHIVED.value
        persisted.moderator_id = moderator.id
        persisted.comment = comment.strip() or "Отклонено модератором"
        persisted.published = None
        graph.add(
            AuditEvent(
                actor_user_id=moderator.id,
                entity_type="message",
                entity_id=persisted.id,
                action="moderation.reject",
                payload={"status": persisted.status, "comment": persisted.comment},
            )
        )
        graph.save(active_store)
        return persisted
    recommendation.status = MessageStatus.ARCHIVED.value
    recommendation.moderator_id = moderator.id
    recommendation.comment = comment.strip() or "Отклонено модератором"
    recommendation.published = None
    await _record_audit(
        session,
        actor_user_id=moderator.id,
        entity_id=recommendation.id,
        action="moderation.reject",
        payload={"status": recommendation.status, "comment": recommendation.comment},
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
        entity_type="message",
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
    items: list[Message],
    *,
    status_filter: MessageStatus | None,
    query_text: str | None,
) -> list[Message]:
    filtered = items
    if status_filter is not None:
        filtered = [item for item in filtered if item.status == status_filter]
    normalized = (query_text or "").strip().lower()
    if not normalized:
        return filtered
    return [item for item in filtered if _moderation_item_matches(item, normalized)]


def _moderation_item_matches(item: Message, normalized: str) -> bool:
    parts = [
        item.title,
        item.comment,
        item.author.display_name if item.author is not None else None,
        item.strategy.title if item.strategy is not None else None,
        item.status,
        item.kind,
    ]
    haystack = " ".join(part.strip().lower() for part in parts if part)
    return normalized in haystack


def _build_queue_stats(
    recommendations: list[Message],
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
        review_count=sum(1 for item in recommendations if item.status == MessageStatus.REVIEW.value),
        scheduled_count=sum(1 for item in recommendations if item.status == MessageStatus.SCHEDULED.value),
        published_count=sum(1 for item in recommendations if item.status == MessageStatus.PUBLISHED.value),
        overdue_review_count=sum(
            1
            for item in recommendations
            if item.status == MessageStatus.REVIEW.value and (now - item.created).total_seconds() > 24 * 3600
        ),
        approved_total=sum(1 for item in events if item.action == "moderation.approve"),
        rework_total=sum(1 for item in events if item.action == "moderation.rework"),
        rejected_total=sum(1 for item in events if item.action == "moderation.reject"),
        avg_resolution_hours=round(sum(resolution_hours) / len(resolution_hours), 1) if resolution_hours else None,
    )
