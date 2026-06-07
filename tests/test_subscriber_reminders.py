from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.audit import AuditEvent
from pitchcopytrade.db.models.catalog import Strategy
from pitchcopytrade.db.models.commerce import Payment, Subscription
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.enums import (
    InstrumentType,
    MessageStatus,
    PaymentProvider,
    PaymentStatus,
    RiskLevel,
    StrategyStatus,
    SubscriptionStatus,
)
from pitchcopytrade.services.subscriber import get_subscriber_status_snapshot, list_reminder_center_entries


class FakeAccessRepository:
    def __init__(self, user: User, message: Message) -> None:
        self.user = user
        self.message = message

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> User | None:
        return self.user if self.user.telegram_user_id == telegram_user_id else None

    async def user_has_active_access(self, user_id: str) -> bool:
        return user_id == self.user.id

    async def list_user_visible_recommendations(self, *, user_id: str, limit: int = 20) -> list[Message]:
        return [self.message][:limit] if user_id == self.user.id else []

    async def list_user_visible_messages(self, *, user_id: str, limit: int = 20) -> list[Message]:
        return await self.list_user_visible_recommendations(user_id=user_id, limit=limit)

    async def list_user_reminder_events(self, *, user_id: str, limit: int = 20):
        event = AuditEvent(
            id="audit-1",
            actor_user_id=None,
            entity_type="user",
            entity_id=user_id,
            action="notification.reminder",
            payload={"user_id": user_id, "title": "Check payment"},
        )
        return [event][:limit]

    async def get_notification_preferences(self, *, user_id: str) -> dict[str, bool]:
        return {"payment_reminders": True, "subscription_reminders": True}

    async def save_notification_preferences(self, *, user_id: str, preferences: dict[str, bool]) -> dict[str, bool]:
        return {"payment_reminders": True, "subscription_reminders": True}


def _make_message() -> Message:
    author_user = User(id="author-user-1", full_name="Alpha Desk")
    author_profile = AuthorProfile(
        id="author-1",
        user_id="author-user-1",
        display_name="Alpha Desk",
        slug="alpha-desk",
        is_active=True,
    )
    author_profile.user = author_user
    strategy = Strategy(
        id="strategy-1",
        author_id="author-1",
        slug="momentum-ru",
        title="Momentum RU",
        short_description="desc",
        full_description="full",
        risk_level=RiskLevel.MEDIUM,
        status=StrategyStatus.PUBLISHED,
        min_capital_rub=150000,
        is_public=True,
    )
    strategy.author = author_profile
    message = Message(
        id="msg-1",
        strategy_id="strategy-1",
        author_id="author-1",
        kind="idea",
        status=MessageStatus.PUBLISHED,
        type="mixed",
        title="Покупка SBER",
        text={"body": "<p>Сильный спрос</p>", "plain": "Сильный спрос"},
        documents=[],
        deals=[],
        published=datetime(2026, 3, 11, tzinfo=timezone.utc),
    )
    message.strategy = strategy
    message.author = author_profile
    return message


@pytest.mark.asyncio
async def test_subscriber_status_snapshot_collects_message_titles() -> None:
    user = User(
        id="user-1",
        email="lead@example.com",
        full_name="Lead User",
        telegram_user_id=12345,
        timezone="Europe/Moscow",
    )
    user.subscriptions = [
        Subscription(
            id="sub-1",
            user_id="user-1",
            product_id="product-1",
            status=SubscriptionStatus.ACTIVE,
            autorenew_enabled=True,
            is_trial=False,
            manual_discount_rub=0,
            start_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            end_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
    ]
    user.payments = [
        Payment(
            id="payment-1",
            user_id="user-1",
            product_id="product-1",
            provider=PaymentProvider.TBANK,
            status=PaymentStatus.PENDING,
            amount_rub=499,
            discount_rub=0,
            final_amount_rub=499,
            currency="RUB",
            external_id="tb-1",
            stub_reference="TB-1",
        )
    ]

    snapshot = await get_subscriber_status_snapshot(FakeAccessRepository(user, _make_message()), telegram_user_id=12345)

    assert snapshot is not None
    assert snapshot.has_access is True
    assert snapshot.visible_message_titles == ["Покупка SBER"]


@pytest.mark.asyncio
async def test_reminder_center_entries_use_audit_payloads() -> None:
    user = User(id="user-1", telegram_user_id=12345, full_name="Lead User")
    entries = await list_reminder_center_entries(FakeAccessRepository(user, _make_message()), user_id="user-1", limit=5)

    assert len(entries) == 1
    assert entries[0].title == "Check payment"
    assert entries[0].kind == "reminder"
