from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from pitchcopytrade.api.deps.repositories import get_access_repository, get_auth_repository, get_public_repository
from pitchcopytrade.api.main import create_app
from pitchcopytrade.auth.passwords import hash_password
from pitchcopytrade.auth.session import build_telegram_fallback_cookie_value
from pitchcopytrade.bot.dispatcher import build_dispatcher
from pitchcopytrade.db.models.accounts import AuthorProfile, Role, User
from pitchcopytrade.db.models.catalog import Instrument, Strategy
from pitchcopytrade.db.models.commerce import Payment, Subscription
from pitchcopytrade.db.models.content import Recommendation, RecommendationAttachment, RecommendationLeg
from pitchcopytrade.db.models.enums import (
    InstrumentType,
    PaymentProvider,
    PaymentStatus,
    RecommendationKind,
    RecommendationStatus,
    RiskLevel,
    RoleSlug,
    StrategyStatus,
    SubscriptionStatus,
    TradeSide,
)


class FakeAuthRepository:
    def __init__(self, user: User | None = None) -> None:
        self.users_by_id: dict[str, User] = {}
        if user is not None:
            self.users_by_id[user.id] = user

    async def get_user_by_identity(self, identity: str) -> User | None:
        return None

    async def get_user_by_id(self, user_id: str) -> User | None:
        return self.users_by_id.get(user_id)


class FakeAccessRepository:
    def __init__(self, user: User) -> None:
        self.user = user

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> User | None:
        return self.user if self.user.telegram_user_id == telegram_user_id else None

    async def user_has_active_access(self, user_id: str) -> bool:
        return False

    async def list_user_visible_recommendations(self, *, user_id: str, limit: int = 20) -> list[Recommendation]:
        return []

    async def get_user_visible_recommendation(self, *, user_id: str, recommendation_id: str) -> Recommendation | None:
        return None

    async def commit(self) -> None:
        return None


class FakePublicRepository:
    def __init__(self, user: User) -> None:
        self.user = user

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> User | None:
        return self.user if self.user.telegram_user_id == telegram_user_id else None

    async def get_user_payment(self, *, telegram_user_id: int, payment_id: str) -> Payment | None:
        user = await self.get_user_by_telegram_id(telegram_user_id)
        if user is None:
            return None
        return next((item for item in user.payments if item.id == payment_id), None)

    async def get_user_subscription(self, *, telegram_user_id: int, subscription_id: str) -> Subscription | None:
        user = await self.get_user_by_telegram_id(telegram_user_id)
        if user is None:
            return None
        return next((item for item in user.subscriptions if item.id == subscription_id), None)

    def add(self, entity: object) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def refresh(self, entity: object) -> None:
        return None


def _make_user() -> User:
    user = User(
        id="user-1",
        email="lead@example.com",
        full_name="Lead User",
        password_hash=hash_password("checkout-pass"),
        telegram_user_id=12345,
        timezone="Europe/Moscow",
    )
    user.roles = [Role(slug=RoleSlug.AUTHOR, title="Author")]
    payment = Payment(
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
        provider_payload={"payment_url": "https://pay.example/tb-1"},
    )
    subscription = Subscription(
        id="subscription-1",
        user_id="user-1",
        product_id="product-1",
        payment_id="payment-1",
        status=SubscriptionStatus.ACTIVE,
        autorenew_enabled=True,
        is_trial=False,
        manual_discount_rub=0,
        start_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    payment.subscriptions = [subscription]
    subscription.payment = payment
    user.payments = [payment]
    user.subscriptions = [subscription]
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


def _build_client(user: User) -> TestClient:
    app = create_app()

    async def override_auth_repository():
        return FakeAuthRepository(user)

    async def override_access_repository():
        return FakeAccessRepository(user)

    async def override_public_repository():
        return FakePublicRepository(user)

    app.dependency_overrides[get_auth_repository] = override_auth_repository
    app.dependency_overrides[get_access_repository] = override_access_repository
    app.dependency_overrides[get_public_repository] = override_public_repository
    client = TestClient(app)
    client.cookies.set("pitchcopytrade_session_tg", build_telegram_fallback_cookie_value(user))
    return client


def test_app_feed_shows_no_access_state(monkeypatch) -> None:
    user = _make_user()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.user_has_active_access",
        lambda _repository, user_id: _async_return(False),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.list_user_visible_recommendations",
        lambda _repository, user_id: _async_return([]),
    )

    with _build_client(user) as client:
        response = client.get("/app/feed")

        assert response.status_code == 200
        assert "Активного доступа пока нет" in response.text


def test_app_status_shows_snapshot(monkeypatch) -> None:
    user = _make_user()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.get_subscriber_status_snapshot",
        lambda _repository, telegram_user_id: _async_return(
            SimpleNamespace(
                user=user,
                has_access=True,
                subscriptions=user.subscriptions,
                active_subscriptions=[],
                payments=user.payments,
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
        assert "/app/subscriptions" in response.text
        assert "/app/payments" in response.text


def test_app_feed_shows_visible_recommendations(monkeypatch) -> None:
    user = _make_user()
    recommendation = _make_recommendation()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.user_has_active_access",
        lambda _repository, user_id: _async_return(True),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.list_user_visible_recommendations",
        lambda _repository, user_id: _async_return([recommendation]),
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
        lambda _repository, user_id, recommendation_id: _async_return(recommendation),
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
        lambda _repository, user_id, recommendation_id: _async_return(recommendation),
    )
    monkeypatch.setattr("pitchcopytrade.api.routes.app.MinioStorage", DummyStorage)

    with _build_client(user) as client:
        response = client.get("/app/recommendations/rec-1/attachments/att-1")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/pdf")
        assert "idea.pdf" in response.headers["content-disposition"]


def test_app_payment_detail_renders_actions(monkeypatch) -> None:
    user = _make_user()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.get_subscriber_status_snapshot",
        lambda _repository, telegram_user_id: _async_return(
            SimpleNamespace(
                user=user,
                has_access=True,
                subscriptions=user.subscriptions,
                active_subscriptions=user.subscriptions,
                payments=user.payments,
                pending_payments=user.payments,
                visible_recommendation_titles=[],
            )
        ),
    )

    with _build_client(user) as client:
        response = client.get("/app/payments/payment-1")

        assert response.status_code == 200
        assert "Открыть оплату" in response.text
        assert "Отменить заявку" in response.text


def test_app_subscription_detail_renders_autorenew_toggle(monkeypatch) -> None:
    user = _make_user()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.get_subscriber_status_snapshot",
        lambda _repository, telegram_user_id: _async_return(
            SimpleNamespace(
                user=user,
                has_access=True,
                subscriptions=user.subscriptions,
                active_subscriptions=user.subscriptions,
                payments=user.payments,
                pending_payments=user.payments,
                visible_recommendation_titles=[],
            )
        ),
    )

    with _build_client(user) as client:
        response = client.get("/app/subscriptions/subscription-1")

        assert response.status_code == 200
        assert "Выключить автопродление" in response.text


def test_app_payment_cancel_updates_status(monkeypatch) -> None:
    user = _make_user()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.get_subscriber_status_snapshot",
        lambda _repository, telegram_user_id: _async_return(
            SimpleNamespace(
                user=user,
                has_access=True,
                subscriptions=user.subscriptions,
                active_subscriptions=user.subscriptions,
                payments=user.payments,
                pending_payments=user.payments,
                visible_recommendation_titles=[],
            )
        ),
    )

    with _build_client(user) as client:
        response = client.post("/app/payments/payment-1/cancel", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/app/payments/payment-1"
        assert user.payments[0].status is PaymentStatus.CANCELLED


def test_app_subscription_autorenew_toggle_updates_state(monkeypatch) -> None:
    user = _make_user()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.get_subscriber_status_snapshot",
        lambda _repository, telegram_user_id: _async_return(
            SimpleNamespace(
                user=user,
                has_access=True,
                subscriptions=user.subscriptions,
                active_subscriptions=user.subscriptions,
                payments=user.payments,
                pending_payments=user.payments,
                visible_recommendation_titles=[],
            )
        ),
    )

    with _build_client(user) as client:
        response = client.post(
            "/app/subscriptions/subscription-1/autorenew",
            data={"enabled": "0"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/app/subscriptions/subscription-1"
        assert user.subscriptions[0].autorenew_enabled is False


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
        lambda _repository, user_id, recommendation_id: _async_return(recommendation),
    )
    monkeypatch.setattr("pitchcopytrade.api.routes.app.LocalFilesystemStorage", DummyLocalStorage)

    with _build_client(user) as client:
        response = client.get("/app/recommendations/rec-1/attachments/att-1")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/pdf")
        assert response.content == b"%PDF-local"


def test_build_dispatcher_registers_only_base_subscriber_commands() -> None:
    dispatcher = build_dispatcher()
    registered_handlers = dispatcher.message.handlers

    assert len(registered_handlers) == 2
    assert len(dispatcher.callback_query.handlers) == 0


async def _async_return(value):
    return value
