from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from pitchcopytrade.api.deps.repositories import get_access_repository, get_auth_repository
from pitchcopytrade.api.main import create_app
from pitchcopytrade.auth.session import build_telegram_fallback_cookie_value
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.catalog import SubscriptionProduct
from pitchcopytrade.db.models.commerce import PromoCode, Subscription
from pitchcopytrade.db.models.enums import BillingPeriod, ProductType, SubscriptionStatus
from pitchcopytrade.repositories.access import SqlAlchemyAccessRepository


class FakeAuthRepository:
    def __init__(self, user: User | None = None) -> None:
        self.user = user

    async def get_user_by_id(self, user_id: str) -> User | None:
        if self.user is not None and self.user.id == user_id:
            return self.user
        return None


class FakeAccessRepository:
    pass


class _ScalarResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


class _QueryCapturingSession:
    def __init__(self, user: User | None) -> None:
        self.user = user
        self.last_query = None

    async def execute(self, query: Any) -> _ScalarResult:
        self.last_query = query
        return _ScalarResult(self.user)


def _build_client(
    *,
    auth_repository: FakeAuthRepository | None = None,
    access_repository: FakeAccessRepository | None = None,
) -> TestClient:
    app = create_app()

    async def override_auth_repository():
        return auth_repository or FakeAuthRepository()

    async def override_access_repository():
        return access_repository or FakeAccessRepository()

    app.dependency_overrides[get_auth_repository] = override_auth_repository
    app.dependency_overrides[get_access_repository] = override_access_repository
    return TestClient(app)


def _make_product() -> SubscriptionProduct:
    return SubscriptionProduct(
        id="product-1",
        product_type=ProductType.STRATEGY,
        slug="momentum-ru-month",
        title="Momentum RU",
        description="Месячная подписка",
        strategy_id=None,
        author_id=None,
        bundle_id=None,
        billing_period=BillingPeriod.MONTH,
        price_rub=499,
        trial_days=7,
        is_active=True,
        autorenew_allowed=True,
    )


def _make_subscription(
    *,
    product: SubscriptionProduct,
    applied_promo_code: PromoCode | None = None,
    manual_discount_rub: int = 0,
) -> Subscription:
    subscription = Subscription(
        id="subscription-1",
        user_id="user-1",
        product_id=product.id,
        payment_id=None,
        status=SubscriptionStatus.ACTIVE,
        autorenew_enabled=True,
        is_trial=True,
        manual_discount_rub=manual_discount_rub,
        start_at=datetime(2026, 3, 11, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
    )
    subscription.product = product
    subscription.applied_promo_code = applied_promo_code
    subscription.applied_promo_code_id = applied_promo_code.id if applied_promo_code is not None else None
    if applied_promo_code is not None:
        applied_promo_code.subscriptions = [subscription]
    return subscription


def _make_snapshot(user: User, subscription: Subscription) -> SimpleNamespace:
    return SimpleNamespace(
        user=user,
        has_access=True,
        subscriptions=[subscription],
        active_subscriptions=[subscription],
        payments=[],
        pending_payments=[],
        visible_message_titles=["Покупка SBER"],
    )


def _build_user() -> User:
    return User(
        id="user-1",
        telegram_user_id=12345,
        username="leaduser",
        full_name="Lead User",
        email="lead@example.com",
        timezone="Europe/Moscow",
    )


def _client_with_snapshot(user: User) -> TestClient:
    return _build_client(
        auth_repository=FakeAuthRepository(user),
        access_repository=FakeAccessRepository(),
    )


def _prepare_app_snapshot(monkeypatch, snapshot: SimpleNamespace) -> None:
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.get_subscriber_status_snapshot",
        lambda _repository, telegram_user_id: _async_return(snapshot),
    )


async def _async_return(value):
    return value


def test_app_subscriptions_renders_without_promo_code(monkeypatch, capsys) -> None:
    user = _build_user()
    product = _make_product()
    subscription = _make_subscription(product=product)
    snapshot = _make_snapshot(user, subscription)
    _prepare_app_snapshot(monkeypatch, snapshot)

    with _client_with_snapshot(user) as client:
        client.cookies.set("pitchcopytrade_session_tg", build_telegram_fallback_cookie_value(user))
        response = client.get("/app/subscriptions")

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert response.status_code == 200
    assert "Подписки" in response.text
    assert "Momentum RU" in response.text
    assert "Промокод:" not in response.text
    assert "Ручная скидка:" not in response.text
    assert "('subs_render'" in combined
    assert "'-'" in combined


def test_app_subscriptions_renders_with_promo_code_and_manual_discount(monkeypatch, capsys) -> None:
    user = _build_user()
    product = _make_product()
    promo_code = PromoCode(
        id="promo-1",
        code="WELCOME10",
        description="Welcome",
        discount_percent=10,
        is_active=True,
        max_redemptions=100,
        current_redemptions=3,
    )
    subscription = _make_subscription(product=product, applied_promo_code=promo_code, manual_discount_rub=150)
    snapshot = _make_snapshot(user, subscription)
    _prepare_app_snapshot(monkeypatch, snapshot)

    with _client_with_snapshot(user) as client:
        client.cookies.set("pitchcopytrade_session_tg", build_telegram_fallback_cookie_value(user))
        response = client.get("/app/subscriptions")

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert response.status_code == 200
    assert "Промокод: WELCOME10" in response.text
    assert "Ручная скидка: 150 руб" in response.text
    assert "('subs_render'" in combined


def test_app_subscription_detail_renders_with_promo_code_and_manual_discount(monkeypatch, capsys) -> None:
    user = _build_user()
    product = _make_product()
    promo_code = PromoCode(
        id="promo-1",
        code="WELCOME10",
        description="Welcome",
        discount_percent=10,
        is_active=True,
        max_redemptions=100,
        current_redemptions=3,
    )
    subscription = _make_subscription(product=product, applied_promo_code=promo_code, manual_discount_rub=150)
    snapshot = _make_snapshot(user, subscription)
    _prepare_app_snapshot(monkeypatch, snapshot)

    with _client_with_snapshot(user) as client:
        client.cookies.set("pitchcopytrade_session_tg", build_telegram_fallback_cookie_value(user))
        response = client.get("/app/subscriptions/subscription-1")

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert response.status_code == 200
    assert "Подписка" in response.text
    assert "Промокод:" in response.text
    assert "WELCOME10" in response.text
    assert "Ручная скидка:" in response.text
    assert "150 руб" in response.text
    assert "('sub_detail'" in combined


@pytest.mark.asyncio
async def test_access_repository_prefetches_applied_promo_code() -> None:
    user = User(id="user-1", telegram_user_id=12345, full_name="Lead User")
    session = _QueryCapturingSession(user)
    repository = SqlAlchemyAccessRepository(session=session)

    result = await repository.get_user_by_telegram_id(12345)

    assert result is user
    assert session.last_query is not None
    option_paths = [str(getattr(option, "path", "")) for option in session.last_query._with_options]
    assert any("Subscription.product" in path for path in option_paths)
    assert any("Subscription.payment" in path for path in option_paths)
    assert any("Subscription.applied_promo_code" in path for path in option_paths)


def test_app_subscription_pages_emit_compact_render_failure_trace(monkeypatch, capsys) -> None:
    user = _build_user()
    product = _make_product()
    subscription = _make_subscription(product=product)
    snapshot = _make_snapshot(user, subscription)
    _prepare_app_snapshot(monkeypatch, snapshot)

    def fail_template_response(*_args, **_kwargs):
        raise RuntimeError("template boom")

    monkeypatch.setattr("pitchcopytrade.api.routes.app.templates.TemplateResponse", fail_template_response)

    with _client_with_snapshot(user) as client:
        client.cookies.set("pitchcopytrade_session_tg", build_telegram_fallback_cookie_value(user))
        with pytest.raises(RuntimeError):
            client.get("/app/subscriptions")

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "('subs_render_fail'" in combined
    assert "template_render_error" in combined
    assert "RuntimeError" in combined
