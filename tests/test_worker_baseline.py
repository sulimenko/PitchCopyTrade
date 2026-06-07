from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import Subscription
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.enums import MessageStatus, ProductType, RiskLevel, StrategyStatus, SubscriptionStatus, UserStatus
from pitchcopytrade.repositories.file_store import FileDataStore
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.worker.jobs import placeholders


def _build_file_runtime_graph(tmp_path):
    store = FileDataStore(root_dir=tmp_path / "runtime", seed_dir=tmp_path / "runtime")
    graph = FileDatasetGraph.load(store)

    author_user = User(id="author-user-1", email="author@example.com", username="author1", full_name="Author", timezone="Europe/Moscow", status=UserStatus.ACTIVE)
    subscriber = User(
        id="subscriber-1",
        email="subscriber@example.com",
        telegram_user_id=777000,
        username="subscriber1",
        full_name="Subscriber",
        timezone="Europe/Moscow",
        status=UserStatus.ACTIVE,
    )
    author = AuthorProfile(id="author-1", user_id="author-user-1", display_name="Alpha Desk", slug="alpha-desk", is_active=True)
    author.user = author_user
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
    strategy.author = author
    product = SubscriptionProduct(
        id="product-1",
        product_type=ProductType.STRATEGY,
        slug="momentum-ru-month",
        title="Momentum RU Monthly",
        description="Monthly access",
        strategy_id=strategy.id,
        duration_days=30,
        price_rub=4900,
        trial_days=0,
        is_active=True,
        autorenew_allowed=True,
    )
    subscription = Subscription(
        id="subscription-1",
        user_id=subscriber.id,
        product_id=product.id,
        status=SubscriptionStatus.ACTIVE,
        autorenew_enabled=True,
        is_trial=False,
        manual_discount_rub=0,
        start_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    message = Message(
        id="msg-1",
        strategy_id=strategy.id,
        author_id=author.id,
        kind="idea",
        type="mixed",
        status=MessageStatus.SCHEDULED,
        title="Покупка SBER",
        text={"body": "<p>Сильный спрос</p>", "plain": "Сильный спрос"},
        documents=[],
        deals=[],
        schedule=datetime(2026, 3, 12, tzinfo=timezone.utc),
    )
    message.strategy = strategy
    message.author = author

    for entity in (author_user, subscriber, author, strategy, product, subscription, message):
        graph.add(entity)
    graph.save(store)
    return store, graph


@pytest.mark.asyncio
async def test_run_scheduled_publish_updates_message_and_notifies_file_runtime(tmp_path, monkeypatch) -> None:
    store, _graph = _build_file_runtime_graph(tmp_path)
    notifier = AsyncMock()
    fake_bot = type("FakeBot", (), {"session": type("Session", (), {"close": AsyncMock()})()})()

    monkeypatch.setattr(placeholders, "AsyncSessionLocal", None)
    monkeypatch.setattr(placeholders, "FileDataStore", lambda: store)
    monkeypatch.setattr(placeholders, "create_bot", lambda _token: fake_bot)
    monkeypatch.setattr(placeholders, "deliver_message_notifications_file", AsyncMock(return_value=[777000]))

    await placeholders.run_scheduled_publish()

    refreshed = FileDatasetGraph.load(store)
    message = refreshed.messages["msg-1"]

    assert message.status == MessageStatus.PUBLISHED.value
    assert message.published is not None
    placeholders.deliver_message_notifications_file.assert_awaited()


def test_bot_broadcast_format_is_html_safe() -> None:
    from pitchcopytrade.bot.main import _format_message

    author_user = User(id="author-user-1", full_name="Alpha Desk", status=UserStatus.ACTIVE)
    author = AuthorProfile(id="author-1", user_id="author-user-1", display_name="Alpha Desk", slug="alpha-desk", is_active=True)
    author.user = author_user
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
    strategy.author = author
    message = Message(
        id="msg-1",
        strategy_id="strategy-1",
        author_id="author-1",
        kind="idea",
        type="mixed",
        status="published",
        title="Покупка SBER",
        text={"body": "<p>Сильный спрос</p>", "plain": "Сильный спрос"},
        documents=[],
        deals=[{"instrument_id": "SBER", "side": "buy"}],
    )
    message.strategy = strategy

    text = _format_message(message, strategy)

    assert "<b>Новая публикация</b>" in text
    assert "<b>Покупка SBER</b>" in text
    assert "<p>Сильный спрос</p>" in text
    assert "SBER" in text
