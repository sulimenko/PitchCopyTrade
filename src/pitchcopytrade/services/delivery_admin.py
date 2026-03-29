from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.accounts import AuthorProfile
from pitchcopytrade.db.models.audit import AuditEvent
from pitchcopytrade.db.models.catalog import Strategy
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.enums import MessageStatus
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore
from pitchcopytrade.services.notifications import (
    deliver_message_notifications,
    deliver_message_notifications_file,
)


DELIVERY_ACTIONS = {"notification.delivery", "worker.scheduled_publish"}


@dataclass(slots=True)
class DeliveryRecord:
    message: Message
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
            [item for item in graph.messages.values() if item.published is not None],
            key=lambda item: (item.published, item.updated),
            reverse=True,
        )
        return [_build_delivery_record(item, _events_for_message(graph.audit_events.values(), item.id)) for item in recommendations]

    recommendations = await _list_published_recommendations(session)
    events = await _list_delivery_events(session)
    return [_build_delivery_record(item, _events_for_message(events, item.id)) for item in recommendations]


async def get_admin_delivery_record(
    session: AsyncSession | None,
    message_id: str,
    *,
    store: FileDataStore | None = None,
) -> DeliveryRecord | None:
    if session is None:
        graph, _store = _file_delivery_graph(store)
        message = graph.messages.get(message_id)
        if message is None:
            return None
        return _build_delivery_record(message, _events_for_message(graph.audit_events.values(), message.id))

    message = await _get_published_message(session, message_id)
    if message is None:
        return None
    events = await _list_delivery_events(session)
    return _build_delivery_record(message, _events_for_message(events, message.id))


async def retry_message_delivery(
    session: AsyncSession | None,
    message_id: str,
    notifier,
    *,
    store: FileDataStore | None = None,
) -> DeliveryRecord:
    if session is None:
        graph, runtime_store = _file_delivery_graph(store)
        message = graph.messages.get(message_id)
        if message is None:
            raise ValueError("Message not found")
        if message.published is None:
            raise ValueError("Повторно отправлять можно только опубликованное сообщение")
        await deliver_message_notifications_file(
            graph,
            runtime_store,
            message,
            notifier,
            trigger="manual_retry",
        )
        return _build_delivery_record(message, _events_for_message(graph.audit_events.values(), message.id))

    message = await _get_published_message(session, message_id)
    if message is None:
        raise ValueError("Message not found")
    if message.published is None:
        raise ValueError("Повторно отправлять можно только опубликованное сообщение")
    await deliver_message_notifications(session, message, notifier, trigger="manual_retry")
    events = await _list_delivery_events(session)
    return _build_delivery_record(message, _events_for_message(events, message.id))


def _build_delivery_record(message: Message, events: list[AuditEvent]) -> DeliveryRecord:
    delivery_events = [item for item in events if item.action == "notification.delivery"]
    latest_delivery_event = delivery_events[0] if delivery_events else None
    delivered_recipients = sum(int((item.payload or {}).get("recipient_count", 0)) for item in delivery_events)
    return DeliveryRecord(
        message=message,
        events=events,
        latest_delivery_event=latest_delivery_event,
        delivery_attempts=len(delivery_events),
        delivered_recipients=delivered_recipients,
    )


def _events_for_message(events, message_id: str) -> list[AuditEvent]:
    return sorted(
        [
            item
            for item in events
            if item.entity_type == "message"
            and item.entity_id == message_id
            and item.action in DELIVERY_ACTIONS
        ],
        key=lambda item: item.created_at,
        reverse=True,
    )


async def _list_published_recommendations(session: AsyncSession) -> list[Message]:
    query = (
        select(Message)
        .options(
            selectinload(Message.strategy).selectinload(Strategy.author).selectinload(AuthorProfile.user),
            selectinload(Message.author).selectinload(AuthorProfile.user),
            selectinload(Message.bundle),
        )
        .where(
            Message.status == MessageStatus.PUBLISHED.value,
            Message.published.is_not(None),
        )
        .order_by(Message.published.desc(), Message.updated.desc())
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def _get_published_message(session: AsyncSession, message_id: str) -> Message | None:
    query = (
        select(Message)
        .options(
            selectinload(Message.strategy).selectinload(Strategy.author).selectinload(AuthorProfile.user),
            selectinload(Message.author).selectinload(AuthorProfile.user),
            selectinload(Message.bundle),
        )
        .where(Message.id == message_id)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def _list_delivery_events(session: AsyncSession) -> list[AuditEvent]:
    query = (
        select(AuditEvent)
        .options(selectinload(AuditEvent.actor_user))
        .where(
            AuditEvent.entity_type == "message",
            AuditEvent.action.in_(DELIVERY_ACTIONS),
        )
        .order_by(AuditEvent.created_at.desc())
    )
    result = await session.execute(query)
    return list(result.scalars().all())
