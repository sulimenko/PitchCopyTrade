from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.enums import MessageKind, MessageStatus
from pitchcopytrade.services.publishing import publish_due_recommendations


class FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class FakeSession:
    def __init__(self, items):
        self.items = items
        self.added = []
        self.committed = False
        self.refreshed = []

    async def execute(self, query):
        return FakeResult(self.items)

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.committed = True

    async def refresh(self, item):
        self.refreshed.append(item.id)


@pytest.mark.asyncio
async def test_publish_due_recommendations_updates_status_and_audit() -> None:
    recommendation = Message(
        id="rec-1",
        strategy_id="strategy-1",
        author_id="author-1",
        kind=MessageKind.IDEA.value,
        status=MessageStatus.SCHEDULED.value,
        schedule=datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc),
        thread="rec-1",
        type="mixed",
        moderation="required",
    )
    session = FakeSession([recommendation])

    published = await publish_due_recommendations(session, now=datetime(2026, 3, 11, 13, 0, tzinfo=timezone.utc))

    assert len(published) == 1
    assert recommendation.status == MessageStatus.PUBLISHED.value
    assert recommendation.schedule is None
    assert recommendation.published == datetime(2026, 3, 11, 13, 0, tzinfo=timezone.utc)
    assert session.committed is True
    assert session.added
