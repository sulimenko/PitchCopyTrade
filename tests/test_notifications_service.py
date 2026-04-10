from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Instrument, Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import Subscription
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.enums import ProductType, RiskLevel, StrategyStatus, SubscriptionStatus, UserStatus
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore
from pitchcopytrade.services.notifications import (
    _recipient_selection_reason,
    _subscription_matches_message,
    _send_with_retry,
    build_message_email_text,
    build_message_notification_text,
    deliver_message_notifications_file,
)


def test_build_message_notification_text_uses_html_safe_message_payload() -> None:
    author_user = User(id="author-user-1", full_name="Alpha Desk")
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
        status="published",
        type="mixed",
        title="Покупка SBER",
        text={"body": "<p>Сильный спрос</p>", "plain": "Сильный спрос"},
        documents=[
            {
                "id": "doc-1",
                "object_key": "messages/msg-1/file.pdf",
                "original_filename": "idea.pdf",
                "content_type": "application/pdf",
                "size_bytes": 123,
            }
        ],
        deals=[
            {
                "instrument_id": "SBER",
                "side": "buy",
                "entry_from": "101.5",
            }
        ],
        published=datetime(2026, 3, 12, tzinfo=timezone.utc),
    )
    message.strategy = strategy

    text = build_message_notification_text(message)

    assert text.startswith("◻ <b>Покупка SBER</b> · <i>Momentum RU</i>")
    assert "Новая публикация по вашей подписке" not in text
    assert "Тип: idea" not in text
    assert "&lt;p&gt;Сильный спрос&lt;/p&gt;" in text
    assert "🟢 Купить" in text
    assert "<b>Вход:</b> 101.5" in text
    assert "📎 idea.pdf" in text or '<a href="messages/msg-1/file.pdf">idea.pdf</a>' in text
    assert text.index("&lt;p&gt;Сильный спрос&lt;/p&gt;") < text.index("━━━━━━━━━━━━━━━━━━━━") < text.index("<b>SBER</b>  🟢 Купить")


def test_build_message_notification_text_renders_text_and_documents_in_order() -> None:
    message = Message(
        id="msg-2",
        strategy_id="strategy-1",
        author_id="author-1",
        kind="idea",
        status="published",
        type="mixed",
        title="Покупка SBER",
        text={"body": "Сильный спрос", "plain": "Сильный спрос"},
        documents=[{"original_filename": "checklist.pdf"}],
        deals=[],
    )

    text = build_message_notification_text(message)

    assert "Сильный спрос" in text
    assert "<b>Structured сделка</b>" not in text
    assert "📎 checklist.pdf" in text
    assert text.index("Сильный спрос") < text.index("━━━━━━━━━━━━━━━━━━━━") < text.index("📎 checklist.pdf")


def test_build_message_notification_text_renders_text_and_deal_in_order() -> None:
    message = Message(
        id="msg-3",
        strategy_id="strategy-1",
        author_id="author-1",
        kind="idea",
        status="published",
        type="mixed",
        title="Покупка SBER",
        text={"body": "Сильный спрос", "plain": "Сильный спрос"},
        documents=[],
        deals=[{"ticker": "SBER", "side": "sell", "entry_from": "101.5", "quantity": "2"}],
    )

    text = build_message_notification_text(message)

    assert "Сильный спрос" in text
    assert "<b>Structured сделка</b>" not in text
    assert "<b>SBER</b>  🔴 Продать" in text
    assert "<b>Вход:</b> 101.5" in text
    assert "Документы" not in text
    assert text.index("Сильный спрос") < text.index("━━━━━━━━━━━━━━━━━━━━") < text.index("<b>SBER</b>  🔴 Продать")


def test_build_message_email_text_uses_same_content_order() -> None:
    message = Message(
        id="msg-email",
        strategy_id="strategy-1",
        author_id="author-1",
        kind="idea",
        status="published",
        type="mixed",
        title="Покупка SBER",
        text={"body": "Сильный спрос", "plain": "Сильный спрос"},
        documents=[{"original_filename": "checklist.pdf"}],
        deals=[{"ticker": "SBER", "side": "buy", "entry_from": "101.5"}],
    )

    text = build_message_email_text(message)

    assert "Новая публикация по вашей подписке" in text
    assert "Покупка SBER" in text
    assert "Сильный спрос" in text
    assert "Structured сделка" in text
    assert "Документы" in text
    assert "• checklist.pdf" in text
    assert text.index("Сильный спрос") < text.index("Structured сделка") < text.index("Документы")


@pytest.mark.asyncio
async def test_send_with_retry_recovers_after_first_failure() -> None:
    send_message = AsyncMock(side_effect=[RuntimeError("temp"), None])

    delivered = await _send_with_retry(send_message, 12345, "hello", attempts=3)

    assert delivered is True
    assert send_message.await_count == 2


def test_recipient_selection_reason_covers_zero_recipient_modes() -> None:
    assert _recipient_selection_reason(
        active_subscriptions=0,
        telegram_bound_active_subscriptions=0,
        matching_active_subscriptions=0,
    ) == "no active subscriptions"
    assert _recipient_selection_reason(
        active_subscriptions=2,
        telegram_bound_active_subscriptions=0,
        matching_active_subscriptions=0,
    ) == "active subscriptions exist but none have telegram_user_id"
    assert _recipient_selection_reason(
        active_subscriptions=2,
        telegram_bound_active_subscriptions=1,
        matching_active_subscriptions=0,
    ) == "active subscriptions exist but do not match message audience"


def test_subscription_matches_message_for_author_and_bundle_targets() -> None:
    author_target_message = Message(
        id="msg-author",
        strategy_id="strategy-1",
        author_id="author-1",
        deliver=["author"],
    )
    bundle_target_message = Message(
        id="msg-bundle",
        strategy_id="strategy-1",
        author_id="author-1",
        bundle_id="bundle-1",
        deliver=["bundle"],
    )
    author_target_product = SubscriptionProduct(
        id="product-author",
        product_type=ProductType.AUTHOR,
        slug="author-month",
        title="Author Monthly",
        author_id="author-1",
        strategy_id=None,
        bundle_id=None,
        duration_days=30,
        price_rub=4900,
        trial_days=0,
        is_active=True,
        autorenew_allowed=True,
    )
    bundle_target_product = SubscriptionProduct(
        id="product-bundle",
        product_type=ProductType.BUNDLE,
        slug="bundle-month",
        title="Bundle Monthly",
        author_id=None,
        strategy_id=None,
        bundle_id="bundle-1",
        duration_days=30,
        price_rub=4900,
        trial_days=0,
        is_active=True,
        autorenew_allowed=True,
    )

    assert _subscription_matches_message(
        author_target_message,
        product=author_target_product,
        bundle_strategy_ids=set(),
    )
    assert _subscription_matches_message(
        bundle_target_message,
        product=bundle_target_product,
        bundle_strategy_ids={"strategy-1"},
    )


@pytest.mark.asyncio
async def test_deliver_message_notifications_file_logs_missing_telegram_identity_reason(
    tmp_path,
    caplog,
) -> None:
    store = FileDataStore(root_dir=tmp_path / "runtime", seed_dir=tmp_path / "runtime")
    graph = FileDatasetGraph.load(store)

    now = datetime(2026, 3, 11, tzinfo=timezone.utc)
    author_user = User(id="author-user-1", full_name="Alpha Desk", status=UserStatus.ACTIVE, timezone="Europe/Moscow")
    subscriber = User(
        id="subscriber-1",
        email=None,
        telegram_user_id=None,
        username="subscriber1",
        full_name="Subscriber One",
        status=UserStatus.ACTIVE,
        timezone="Europe/Moscow",
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
        author_id=None,
        bundle_id=None,
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
        start_at=now,
        end_at=now.replace(month=4),
    )
    subscription.user = subscriber
    subscription.product = product
    subscriber.subscriptions = [subscription]
    product.subscriptions = [subscription]
    message = Message(
        id="message-1",
        strategy_id=strategy.id,
        author_id=author.id,
        kind="idea",
        status="published",
        type="mixed",
        title="Покупка SBER",
        text={"body": "Сильный спрос", "plain": "Сильный спрос"},
        documents=[],
        deals=[],
        deliver=["strategy"],
        published=now,
    )
    message.strategy = strategy
    message.author = author

    for entity in (author_user, subscriber, author, strategy, product, subscription, message):
        graph.add(entity)

    fake_bot = type(
        "FakeBot",
        (),
        {
            "send_message": AsyncMock(),
            "session": type("FakeSession", (), {"close": AsyncMock()})(),
        },
    )()

    with caplog.at_level("WARNING"):
        await deliver_message_notifications_file(graph, store, message, fake_bot, trigger="test_missing_telegram")

    assert fake_bot.send_message.await_count == 0
    assert "fallback skipped" in caplog.text
    assert "reason=no email" in caplog.text


@pytest.mark.asyncio
async def test_deliver_message_notifications_file_falls_back_to_email(
    tmp_path,
    caplog,
    monkeypatch,
) -> None:
    store = FileDataStore(root_dir=tmp_path / "runtime", seed_dir=tmp_path / "runtime")
    graph = FileDatasetGraph.load(store)

    now = datetime(2026, 3, 11, tzinfo=timezone.utc)
    author_user = User(id="author-user-1", full_name="Alpha Desk", status=UserStatus.ACTIVE, timezone="Europe/Moscow")
    subscriber = User(
        id="subscriber-1",
        email="subscriber@example.com",
        telegram_user_id=None,
        username="subscriber1",
        full_name="Subscriber One",
        status=UserStatus.ACTIVE,
        timezone="Europe/Moscow",
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
        author_id=None,
        bundle_id=None,
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
        start_at=now,
        end_at=now.replace(month=4),
    )
    subscription.user = subscriber
    subscription.product = product
    subscriber.subscriptions = [subscription]
    product.subscriptions = [subscription]
    message = Message(
        id="message-1",
        strategy_id=strategy.id,
        author_id=author.id,
        kind="idea",
        status="published",
        type="mixed",
        title="Покупка SBER",
        text={"body": "Сильный спрос", "plain": "Сильный спрос"},
        documents=[],
        deals=[],
        deliver=["strategy"],
        published=now,
    )
    message.strategy = strategy
    message.author = author

    for entity in (author_user, subscriber, author, strategy, product, subscription, message):
        graph.add(entity)

    fake_bot = type(
        "FakeBot",
        (),
        {
            "send_message": AsyncMock(),
            "session": type("FakeSession", (), {"close": AsyncMock()})(),
        },
    )()
    fake_sender = AsyncMock(return_value=(True, None))

    monkeypatch.setattr("pitchcopytrade.services.notifications.send_smtp_email", fake_sender)
    with caplog.at_level("INFO"):
        delivered = await deliver_message_notifications_file(graph, store, message, fake_bot, trigger="test_email_fallback")

    assert delivered == []
    assert fake_bot.send_message.await_count == 0
    assert fake_sender.await_count == 1
    assert "fallback email attempt" in caplog.text


@pytest.mark.asyncio
async def test_deliver_message_notifications_file_falls_back_to_email_after_telegram_failure(
    tmp_path,
    monkeypatch,
) -> None:
    store = FileDataStore(root_dir=tmp_path / "runtime", seed_dir=tmp_path / "runtime")
    graph = FileDatasetGraph.load(store)

    now = datetime(2026, 3, 11, tzinfo=timezone.utc)
    author_user = User(id="author-user-1", full_name="Alpha Desk", status=UserStatus.ACTIVE, timezone="Europe/Moscow")
    subscriber = User(
        id="subscriber-1",
        email="subscriber@example.com",
        telegram_user_id=222,
        username="subscriber1",
        full_name="Subscriber One",
        status=UserStatus.ACTIVE,
        timezone="Europe/Moscow",
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
        author_id=None,
        bundle_id=None,
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
        start_at=now,
        end_at=now.replace(month=4),
    )
    subscription.user = subscriber
    subscription.product = product
    subscriber.subscriptions = [subscription]
    product.subscriptions = [subscription]
    message = Message(
        id="message-1",
        strategy_id=strategy.id,
        author_id=author.id,
        kind="idea",
        status="published",
        type="mixed",
        title="Покупка SBER",
        text={"body": "Сильный спрос", "plain": "Сильный спрос"},
        documents=[],
        deals=[],
        deliver=["strategy"],
        published=now,
    )
    message.strategy = strategy
    message.author = author

    for entity in (author_user, subscriber, author, strategy, product, subscription, message):
        graph.add(entity)

    fake_bot = type(
        "FakeBot",
        (),
        {
            "send_message": AsyncMock(side_effect=RuntimeError("boom")),
            "session": type("FakeSession", (), {"close": AsyncMock()})(),
        },
    )()
    fake_sender = AsyncMock(return_value=(True, None))
    monkeypatch.setattr("pitchcopytrade.services.notifications.send_smtp_email", fake_sender)

    delivered = await deliver_message_notifications_file(graph, store, message, fake_bot, trigger="test_email_fallback")

    assert delivered == []
    assert fake_bot.send_message.await_count >= 1
    assert fake_sender.await_count == 1


@pytest.mark.asyncio
async def test_deliver_message_notifications_file_adds_admin_copy_bcc(
    tmp_path,
    monkeypatch,
) -> None:
    store = FileDataStore(root_dir=tmp_path / "runtime", seed_dir=tmp_path / "runtime")
    graph = FileDatasetGraph.load(store)

    now = datetime(2026, 3, 11, tzinfo=timezone.utc)
    author_user = User(id="author-user-1", full_name="Alpha Desk", status=UserStatus.ACTIVE, timezone="Europe/Moscow")
    subscriber = User(
        id="subscriber-1",
        email="subscriber@example.com",
        telegram_user_id=None,
        username="subscriber1",
        full_name="Subscriber One",
        status=UserStatus.ACTIVE,
        timezone="Europe/Moscow",
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
        author_id=None,
        bundle_id=None,
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
        start_at=now,
        end_at=now.replace(month=4),
    )
    subscription.user = subscriber
    subscription.product = product
    subscriber.subscriptions = [subscription]
    product.subscriptions = [subscription]
    message = Message(
        id="message-1",
        strategy_id=strategy.id,
        author_id=author.id,
        kind="idea",
        status="published",
        type="mixed",
        title="Покупка SBER",
        text={"body": "Сильный спрос", "plain": "Сильный спрос"},
        documents=[],
        deals=[],
        deliver=["strategy"],
        published=now,
    )
    message.strategy = strategy
    message.author = author

    for entity in (author_user, subscriber, author, strategy, product, subscription, message):
        graph.add(entity)

    fake_bot = type(
        "FakeBot",
        (),
        {
            "send_message": AsyncMock(),
            "session": type("FakeSession", (), {"close": AsyncMock()})(),
        },
    )()
    fake_sender = AsyncMock(return_value=(True, None))
    monkeypatch.setattr("pitchcopytrade.services.notifications.send_smtp_email", fake_sender)
    monkeypatch.setattr(
        "pitchcopytrade.services.notifications.get_settings",
        lambda: type("Settings", (), {"admin_email": "admin@example.com"})(),
    )

    delivered = await deliver_message_notifications_file(graph, store, message, fake_bot, trigger="test_admin_copy")

    assert delivered == []
    assert fake_sender.await_count == 1
    assert fake_sender.await_args.kwargs["bcc_emails"] == ("admin@example.com",)


@pytest.mark.asyncio
async def test_deliver_message_notifications_file_logs_audience_mismatch_reason(
    tmp_path,
    caplog,
) -> None:
    store = FileDataStore(root_dir=tmp_path / "runtime", seed_dir=tmp_path / "runtime")
    graph = FileDatasetGraph.load(store)

    now = datetime(2026, 3, 11, tzinfo=timezone.utc)
    author_user = User(id="author-user-1", full_name="Alpha Desk", status=UserStatus.ACTIVE, timezone="Europe/Moscow")
    subscriber = User(
        id="subscriber-1",
        email="subscriber@example.com",
        telegram_user_id=222,
        username="subscriber1",
        full_name="Subscriber One",
        status=UserStatus.ACTIVE,
        timezone="Europe/Moscow",
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
    strategy_mismatch = Strategy(
        id="strategy-2",
        author_id="author-1",
        slug="mean-reversion",
        title="Mean Reversion",
        short_description="desc",
        full_description="full",
        risk_level=RiskLevel.MEDIUM,
        status=StrategyStatus.PUBLISHED,
        min_capital_rub=150000,
        is_public=True,
    )
    strategy.author = author
    strategy_mismatch.author = author
    product = SubscriptionProduct(
        id="product-1",
        product_type=ProductType.STRATEGY,
        slug="momentum-ru-month",
        title="Momentum RU Monthly",
        description="Monthly access",
        strategy_id=strategy.id,
        author_id=None,
        bundle_id=None,
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
        start_at=now,
        end_at=now.replace(month=4),
    )
    subscription.user = subscriber
    subscription.product = product
    subscriber.subscriptions = [subscription]
    product.subscriptions = [subscription]
    message = Message(
        id="message-1",
        strategy_id=strategy_mismatch.id,
        author_id=author.id,
        kind="idea",
        status="published",
        type="mixed",
        title="Покупка SBER",
        text={"body": "Сильный спрос", "plain": "Сильный спрос"},
        documents=[],
        deals=[],
        deliver=["strategy"],
        published=now,
    )
    message.strategy = strategy_mismatch
    message.author = author

    for entity in (author_user, subscriber, author, strategy, strategy_mismatch, product, subscription, message):
        graph.add(entity)

    fake_bot = type(
        "FakeBot",
        (),
        {
            "send_message": AsyncMock(),
            "session": type("FakeSession", (), {"close": AsyncMock()})(),
        },
    )()

    with caplog.at_level("WARNING"):
        await deliver_message_notifications_file(graph, store, message, fake_bot, trigger="test_audience_mismatch")

    assert fake_bot.send_message.await_count == 0
    assert "active subscriptions exist but do not match message audience" in caplog.text
