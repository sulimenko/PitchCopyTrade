from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from pitchcopytrade.api.deps.repositories import get_auth_repository
from pitchcopytrade.api.main import create_app
from pitchcopytrade.auth.passwords import hash_password
from pitchcopytrade.auth.session import build_telegram_fallback_cookie_value, build_telegram_login_link_token
from pitchcopytrade.bot.dispatcher import build_dispatcher
from pitchcopytrade.bot.handlers.feed import handle_feed, handle_payments, handle_status, handle_subscriptions, handle_web
from pitchcopytrade.bot.handlers.shop import handle_buy_confirm, handle_buy_preview, handle_catalog, handle_shop_callback
from pitchcopytrade.db.models.accounts import AuthorProfile, Role, User
from pitchcopytrade.db.models.catalog import Instrument, Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import Payment, Subscription
from pitchcopytrade.db.models.content import Recommendation, RecommendationAttachment, RecommendationLeg
from pitchcopytrade.db.models.enums import (
    BillingPeriod,
    PaymentProvider,
    PaymentStatus,
    ProductType,
    RecommendationKind,
    RecommendationStatus,
    RiskLevel,
    RoleSlug,
    StrategyStatus,
    SubscriptionStatus,
    TradeSide,
    InstrumentType,
)
from pitchcopytrade.db.session import get_db_session


class FakeAsyncSession:
    async def execute(self, query):
        raise AssertionError("This suite expects monkeypatched service calls")


class FakeAuthRepository:
    def __init__(self, user: User | None = None) -> None:
        self.users_by_id: dict[str, User] = {}
        if user is not None:
            self.users_by_id[user.id] = user

    async def get_user_by_identity(self, identity: str) -> User | None:
        return None

    async def get_user_by_id(self, user_id: str) -> User | None:
        return self.users_by_id.get(user_id)


def _make_user() -> User:
    user = User(
        id="user-1",
        email="lead@example.com",
        full_name="Lead User",
        password_hash=hash_password("checkout-pass"),
        timezone="Europe/Moscow",
    )
    user.roles = [Role(slug=RoleSlug.AUTHOR, title="Author")]
    return user


def _make_recommendation() -> Recommendation:
    author_user = User(id="author-user-1", full_name="Alpha Desk")
    author = AuthorProfile(
        id="author-1",
        user_id="author-user-1",
        display_name="Alpha Desk",
        slug="alpha-desk",
        is_active=True,
    )
    author.user = author_user
    strategy = Strategy(
        id="strategy-1",
        author_id="author-1",
        slug="momentum-ru",
        title="Momentum RU",
        short_description="Системная стратегия",
        full_description="Полное описание",
        risk_level=RiskLevel.MEDIUM,
        status=StrategyStatus.PUBLISHED,
        min_capital_rub=150000,
        is_public=True,
    )
    strategy.author = author
    recommendation = Recommendation(
        id="rec-1",
        strategy_id="strategy-1",
        author_id="author-1",
        kind=RecommendationKind.NEW_IDEA,
        status=RecommendationStatus.PUBLISHED,
        title="Покупка SBER",
        summary="Сильный спрос и пробой уровня",
        published_at=datetime(2026, 3, 11, tzinfo=timezone.utc),
    )
    recommendation.strategy = strategy
    recommendation.author = author
    instrument = Instrument(
        id="instrument-1",
        ticker="SBER",
        name="Sberbank",
        board="TQBR",
        lot_size=10,
        currency="RUB",
        instrument_type=InstrumentType.EQUITY,
        is_active=True,
    )
    leg = RecommendationLeg(
        id="leg-1",
        recommendation_id="rec-1",
        instrument_id="instrument-1",
        side=TradeSide.BUY,
        entry_from=101.5,
        stop_loss=99.9,
        take_profit_1=106.2,
        time_horizon="1-3 дня",
        note="Основной сценарий",
    )
    leg.instrument = instrument
    attachment = RecommendationAttachment(
        id="att-1",
        recommendation_id="rec-1",
        storage_provider="minio",
        bucket_name="uploads",
        object_key="recommendations/rec-1/file.pdf",
        original_filename="idea.pdf",
        content_type="application/pdf",
        size_bytes=1234,
    )
    recommendation.legs = [leg]
    recommendation.attachments = [attachment]
    return recommendation


def _make_strategy_with_product() -> tuple[Strategy, SubscriptionProduct]:
    author_user = User(id="author-user-1", full_name="Alpha Desk")
    author = AuthorProfile(
        id="author-1",
        user_id="author-user-1",
        display_name="Alpha Desk",
        slug="alpha-desk",
        is_active=True,
    )
    author.user = author_user
    strategy = Strategy(
        id="strategy-1",
        author_id="author-1",
        slug="momentum-ru",
        title="Momentum RU",
        short_description="Системная стратегия",
        full_description="Полное описание",
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
        strategy_id="strategy-1",
        author_id=None,
        bundle_id=None,
        billing_period=BillingPeriod.MONTH,
        price_rub=4900,
        trial_days=7,
        is_active=True,
        autorenew_allowed=True,
    )
    product.strategy = strategy
    strategy.subscription_products = [product]
    return strategy, product


def _build_client(user: User) -> TestClient:
    app = create_app()

    async def override_db_session():
        yield FakeAsyncSession()

    async def override_auth_repository():
        return FakeAuthRepository(user)

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_auth_repository] = override_auth_repository
    client = TestClient(app)
    client.cookies.set("pitchcopytrade_session_tg", build_telegram_fallback_cookie_value(user))
    return client


def test_app_feed_shows_no_access_state(monkeypatch) -> None:
    user = _make_user()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.user_has_active_access",
        lambda _session, user_id: _async_return(False),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.list_user_visible_recommendations",
        lambda _session, user_id: _async_return([]),
    )

    with _build_client(user) as client:
        response = client.get("/app/feed")

        assert response.status_code == 200
        assert "Активного доступа пока нет" in response.text


def test_app_status_shows_snapshot(monkeypatch) -> None:
    user = _make_user()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.get_subscriber_status_snapshot",
        lambda _session, telegram_user_id: _async_return(
            SimpleNamespace(
                user=user,
                has_access=True,
                active_subscriptions=[],
                pending_payments=[],
                visible_recommendation_titles=["Покупка SBER"],
            )
        ),
    )

    with _build_client(user) as client:
        response = client.get("/app/status")

        assert response.status_code == 200
        assert "Статус подписки" in response.text
        assert "Покупка SBER" in response.text


def test_app_feed_shows_visible_recommendations(monkeypatch) -> None:
    user = _make_user()
    recommendation = _make_recommendation()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.user_has_active_access",
        lambda _session, user_id: _async_return(True),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.list_user_visible_recommendations",
        lambda _session, user_id: _async_return([recommendation]),
    )

    with _build_client(user) as client:
        response = client.get("/app/feed")

        assert response.status_code == 200
        assert "Покупка SBER" in response.text
        assert "/app/recommendations/rec-1" in response.text


def test_recommendation_detail_requires_visible_acl(monkeypatch) -> None:
    user = _make_user()
    recommendation = _make_recommendation()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.get_user_visible_recommendation",
        lambda _session, user_id, recommendation_id: _async_return(recommendation),
    )

    with _build_client(user) as client:
        response = client.get("/app/recommendations/rec-1")

        assert response.status_code == 200
        assert "Покупка SBER" in response.text
        assert "Momentum RU" in response.text
        assert "idea.pdf" in response.text
        assert "tp1 106.2" in response.text


def test_recommendation_attachment_download(monkeypatch) -> None:
    user = _make_user()
    recommendation = _make_recommendation()

    class DummyStorage:
        def __init__(self, bucket_name=None):
            self.bucket_name = bucket_name

        def download_bytes(self, object_key: str) -> bytes:
            assert object_key == "recommendations/rec-1/file.pdf"
            return b"%PDF-1.4"

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.get_user_visible_recommendation",
        lambda _session, user_id, recommendation_id: _async_return(recommendation),
    )
    monkeypatch.setattr("pitchcopytrade.api.routes.app.MinioStorage", DummyStorage)

    with _build_client(user) as client:
        response = client.get("/app/recommendations/rec-1/attachments/att-1")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/pdf")
        assert "idea.pdf" in response.headers["content-disposition"]
        assert response.content == b"%PDF-1.4"


def test_recommendation_attachment_download_from_local_storage(monkeypatch) -> None:
    user = _make_user()
    recommendation = _make_recommendation()
    recommendation.attachments[0].storage_provider = "local_fs"
    recommendation.attachments[0].bucket_name = "blob"

    class DummyLocalStorage:
        def __init__(self, bucket_name=None):
            self.bucket_name = bucket_name

        def download_bytes(self, object_key: str) -> bytes:
            assert object_key == "recommendations/rec-1/file.pdf"
            return b"%PDF-local"

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.get_user_visible_recommendation",
        lambda _session, user_id, recommendation_id: _async_return(recommendation),
    )
    monkeypatch.setattr("pitchcopytrade.api.routes.app.LocalFilesystemStorage", DummyLocalStorage)

    with _build_client(user) as client:
        response = client.get("/app/recommendations/rec-1/attachments/att-1")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/pdf")
        assert response.content == b"%PDF-local"


@pytest.mark.asyncio
async def test_feed_handler_denies_unknown_telegram_user(monkeypatch) -> None:
    message = AsyncMock()
    message.from_user = SimpleNamespace(id=12345)

    class DummySessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("pitchcopytrade.bot.handlers.feed.AsyncSessionLocal", lambda: DummySessionContext())
    monkeypatch.setattr("pitchcopytrade.bot.handlers.feed.get_user_by_telegram_id", lambda _session, _id: _async_return(None))

    await handle_feed(message)

    message.answer.assert_awaited_once()
    assert "Сначала выполните /start" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_feed_handler_returns_visible_items(monkeypatch) -> None:
    user = _make_user()
    recommendation = _make_recommendation()
    message = AsyncMock()
    message.from_user = SimpleNamespace(id=12345)

    class DummySessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("pitchcopytrade.bot.handlers.feed.AsyncSessionLocal", lambda: DummySessionContext())
    monkeypatch.setattr("pitchcopytrade.bot.handlers.feed.get_user_by_telegram_id", lambda _session, _id: _async_return(user))
    monkeypatch.setattr("pitchcopytrade.bot.handlers.feed.user_has_active_access", lambda _session, user_id: _async_return(True))
    monkeypatch.setattr(
        "pitchcopytrade.bot.handlers.feed.list_user_visible_recommendations",
        lambda _session, user_id, limit=5: _async_return([recommendation]),
    )

    await handle_feed(message)

    message.answer.assert_awaited_once()
    sent_text = message.answer.await_args.args[0]
    assert "Ваши доступные рекомендации" in sent_text
    assert "Покупка SBER" in sent_text
    assert "SBER buy 101.5" in sent_text
    assert "1 files" in sent_text


def test_build_dispatcher_registers_feed_handler() -> None:
    dispatcher = build_dispatcher()
    registered_handlers = dispatcher.message.handlers

    assert len(registered_handlers) == 10
    assert len(dispatcher.callback_query.handlers) == 1


@pytest.mark.asyncio
async def test_catalog_handler_lists_products(monkeypatch) -> None:
    strategy, product = _make_strategy_with_product()
    message = AsyncMock()

    class DummySessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("pitchcopytrade.bot.handlers.shop.AsyncSessionLocal", lambda: DummySessionContext())
    monkeypatch.setattr("pitchcopytrade.bot.handlers.shop.list_public_strategies", lambda _session: _async_return([strategy]))

    await handle_catalog(message)

    sent_texts = [call.args[0] for call in message.answer.await_args_list]
    assert any("Momentum RU" in text for text in sent_texts)
    assert any(product.slug in text for text in sent_texts)
    assert any("Быстрый выбор продукта" in text for text in sent_texts)


@pytest.mark.asyncio
async def test_buy_preview_handler_shows_confirm_command(monkeypatch) -> None:
    _strategy, product = _make_strategy_with_product()
    message = AsyncMock()
    command = SimpleNamespace(args=product.slug)

    class DummySessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("pitchcopytrade.bot.handlers.shop.AsyncSessionLocal", lambda: DummySessionContext())
    monkeypatch.setattr("pitchcopytrade.bot.handlers.shop.get_public_product_by_slug", lambda _session, _slug: _async_return(product))

    await handle_buy_preview(message, command)

    sent_text = message.answer.await_args.args[0]
    assert "/confirm_buy" in sent_text
    assert product.title in sent_text
    inline_markup = message.answer.await_args.kwargs["reply_markup"]
    assert inline_markup.inline_keyboard[0][0].callback_data == f"buy_confirm:{product.slug}"


@pytest.mark.asyncio
async def test_buy_confirm_handler_creates_stub_checkout(monkeypatch) -> None:
    _strategy, product = _make_strategy_with_product()
    user = _make_user()
    payment = Payment(
        id="payment-1",
        user_id="user-1",
        product_id="product-1",
        provider=PaymentProvider.STUB_MANUAL,
        status=PaymentStatus.PENDING,
        amount_rub=4900,
        discount_rub=0,
        final_amount_rub=4900,
        currency="RUB",
        stub_reference="MANUAL-MOMENTUM-ABCD1234",
    )
    subscription = Subscription(
        id="subscription-1",
        user_id="user-1",
        product_id="product-1",
        payment_id="payment-1",
        status=SubscriptionStatus.PENDING,
        autorenew_enabled=True,
        is_trial=True,
        manual_discount_rub=0,
        start_at=datetime(2026, 3, 11, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
    )
    result = SimpleNamespace(user=user, payment=payment, subscription=subscription)
    message = AsyncMock()
    message.from_user = SimpleNamespace(id=12345, username="leaduser", first_name="Lead", last_name="User")
    command = SimpleNamespace(args=product.slug)

    class DummySessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("pitchcopytrade.bot.handlers.shop.AsyncSessionLocal", lambda: DummySessionContext())
    monkeypatch.setattr("pitchcopytrade.bot.handlers.shop.get_public_product_by_slug", lambda _session, _slug: _async_return(product))
    monkeypatch.setattr("pitchcopytrade.bot.handlers.shop.create_telegram_stub_checkout", lambda _session, product, profile: _async_return(result))

    await handle_buy_confirm(message, command)

    sent_text = message.answer.await_args.args[0]
    assert "Заявка на оплату создана" in sent_text
    assert "MANUAL-MOMENTUM-ABCD1234" in sent_text


@pytest.mark.asyncio
async def test_shop_callback_preview_opens_product(monkeypatch) -> None:
    _strategy, product = _make_strategy_with_product()
    callback = AsyncMock()
    callback.data = f"buy_preview:{product.slug}"
    callback.message = AsyncMock()

    class DummySessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("pitchcopytrade.bot.handlers.shop.AsyncSessionLocal", lambda: DummySessionContext())
    monkeypatch.setattr("pitchcopytrade.bot.handlers.shop.get_public_product_by_slug", lambda _session, _slug: _async_return(product))

    await handle_shop_callback(callback)

    sent_text = callback.message.answer.await_args.args[0]
    assert product.title in sent_text
    callback.answer.assert_awaited()


@pytest.mark.asyncio
async def test_web_handler_returns_telegram_auth_link(monkeypatch) -> None:
    user = _make_user()
    message = AsyncMock()
    message.from_user = SimpleNamespace(id=12345)

    class DummySessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("pitchcopytrade.bot.handlers.feed.AsyncSessionLocal", lambda: DummySessionContext())
    monkeypatch.setattr("pitchcopytrade.bot.handlers.feed.get_user_by_telegram_id", lambda _session, _id: _async_return(user))

    await handle_web(message)

    sent_text = message.answer.await_args.args[0]
    assert "/tg-auth?token=" in sent_text
    assert "Верификация через Telegram" in sent_text
    assert "next=/app/status" in sent_text


@pytest.mark.asyncio
async def test_status_handler_returns_access_summary(monkeypatch) -> None:
    user = _make_user()
    product = SubscriptionProduct(
        id="product-1",
        product_type=ProductType.STRATEGY,
        slug="momentum-ru-month",
        title="Momentum RU Monthly",
        strategy_id="strategy-1",
        author_id=None,
        bundle_id=None,
        billing_period=BillingPeriod.MONTH,
        price_rub=4900,
        trial_days=7,
        is_active=True,
        autorenew_allowed=True,
    )
    payment = Payment(
        id="payment-1",
        user_id=user.id,
        product_id=product.id,
        provider=PaymentProvider.STUB_MANUAL,
        status=PaymentStatus.PENDING,
        amount_rub=4900,
        discount_rub=0,
        final_amount_rub=4900,
        currency="RUB",
        stub_reference="MANUAL-MOMENTUM-ABCD1234",
    )
    payment.product = product
    subscription = Subscription(
        id="subscription-1",
        user_id=user.id,
        product_id=product.id,
        payment_id=payment.id,
        status=SubscriptionStatus.ACTIVE,
        autorenew_enabled=True,
        is_trial=False,
        manual_discount_rub=0,
        start_at=datetime(2026, 3, 11, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
    )
    subscription.product = product
    user.payments = [payment]
    user.subscriptions = [subscription]
    message = AsyncMock()
    message.from_user = SimpleNamespace(id=12345)

    class DummySessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("pitchcopytrade.bot.handlers.feed.AsyncSessionLocal", lambda: DummySessionContext())
    monkeypatch.setattr(
        "pitchcopytrade.bot.handlers.feed.get_subscriber_status_snapshot",
        lambda _session, telegram_user_id: _async_return(
            SimpleNamespace(
                user=user,
                has_access=True,
                active_subscriptions=[subscription],
                pending_payments=[payment],
                visible_recommendation_titles=["Покупка SBER"],
            )
        ),
    )

    await handle_status(message)

    sent_text = message.answer.await_args.args[0]
    assert "Статус подписчика PitchCopyTrade" in sent_text
    assert "Momentum RU Monthly" in sent_text
    assert "Покупка SBER" in sent_text


@pytest.mark.asyncio
async def test_bot_subscriptions_uses_snapshot(monkeypatch) -> None:
    user = _make_user()
    _strategy, product = _make_strategy_with_product()
    subscription = Subscription(
        id="subscription-1",
        user_id=user.id,
        product_id=product.id,
        status=SubscriptionStatus.ACTIVE,
        autorenew_enabled=True,
        is_trial=False,
        manual_discount_rub=0,
        start_at=datetime(2026, 3, 11, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
    )
    subscription.product = product
    message = AsyncMock()
    message.from_user = SimpleNamespace(id=12345)

    class DummySessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("pitchcopytrade.bot.handlers.feed.AsyncSessionLocal", lambda: DummySessionContext())
    monkeypatch.setattr(
        "pitchcopytrade.bot.handlers.feed.get_subscriber_status_snapshot",
        lambda _session, telegram_user_id: _async_return(
            SimpleNamespace(
                user=user,
                has_access=True,
                active_subscriptions=[subscription],
                pending_payments=[],
                visible_recommendation_titles=[],
            )
        ),
    )

    await handle_subscriptions(message)

    sent_text = message.answer.await_args.args[0]
    assert "Мои подписки" in sent_text
    assert "Momentum RU Monthly" in sent_text


@pytest.mark.asyncio
async def test_bot_payments_uses_snapshot(monkeypatch) -> None:
    user = _make_user()
    _strategy, product = _make_strategy_with_product()
    payment = Payment(
        id="payment-1",
        user_id=user.id,
        product_id=product.id,
        provider=PaymentProvider.TBANK,
        status=PaymentStatus.PENDING,
        amount_rub=4900,
        discount_rub=0,
        final_amount_rub=4900,
        currency="RUB",
        external_id="777",
        stub_reference="ORDER-777",
        provider_payload={"payment_url": "https://pay.tbank.ru/qr/777"},
    )
    payment.product = product
    message = AsyncMock()
    message.from_user = SimpleNamespace(id=12345)

    class DummySessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("pitchcopytrade.bot.handlers.feed.AsyncSessionLocal", lambda: DummySessionContext())
    monkeypatch.setattr(
        "pitchcopytrade.bot.handlers.feed.get_subscriber_status_snapshot",
        lambda _session, telegram_user_id: _async_return(
            SimpleNamespace(
                user=user,
                has_access=False,
                active_subscriptions=[],
                pending_payments=[payment],
                visible_recommendation_titles=[],
            )
        ),
    )

    await handle_payments(message)

    sent_text = message.answer.await_args.args[0]
    assert "Мои оплаты" in sent_text
    assert "https://pay.tbank.ru/qr/777" in sent_text


async def _async_return(value):
    return value
