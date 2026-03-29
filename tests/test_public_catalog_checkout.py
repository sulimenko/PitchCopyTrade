from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from pitchcopytrade.api.deps.repositories import get_access_repository, get_auth_repository, get_public_repository
from pitchcopytrade.api.main import create_app
from pitchcopytrade.auth.session import build_telegram_fallback_cookie_value
from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import LegalDocument, Payment, PromoCode, Subscription
from pitchcopytrade.db.models.enums import (
    BillingPeriod,
    LegalDocumentType,
    PaymentProvider,
    PaymentStatus,
    ProductType,
    RiskLevel,
    StrategyStatus,
    SubscriptionStatus,
)
from pitchcopytrade.payments.tbank import TBankAcquiringClient


class FakePublicRepository:
    pass


class FakeAuthRepository:
    def __init__(self, user: User | None = None) -> None:
        self.user = user

    async def get_user_by_id(self, user_id: str) -> User | None:
        if self.user is not None and self.user.id == user_id:
            return self.user
        return None


class FakeAccessRepository:
    pass


def _build_client(
    repository: FakePublicRepository,
    *,
    auth_repository: FakeAuthRepository | None = None,
    access_repository: FakeAccessRepository | None = None,
) -> TestClient:
    app = create_app()

    async def override_public_repository():
        return repository

    async def override_auth_repository():
        return auth_repository or FakeAuthRepository()

    async def override_access_repository():
        return access_repository or FakeAccessRepository()

    app.dependency_overrides[get_public_repository] = override_public_repository
    app.dependency_overrides[get_auth_repository] = override_auth_repository
    app.dependency_overrides[get_access_repository] = override_access_repository
    return TestClient(app)


def _make_strategy_and_product() -> tuple[Strategy, SubscriptionProduct]:
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
        short_description="Системная стратегия на российские акции",
        full_description="Полное описание стратегии",
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
        title="Momentum RU",
        description="Месячная подписка",
        strategy_id="strategy-1",
        author_id=None,
        bundle_id=None,
        billing_period=BillingPeriod.MONTH,
        price_rub=499,
        trial_days=7,
        is_active=True,
        autorenew_allowed=True,
    )
    product.strategy = strategy
    strategy.subscription_products = [product]
    return strategy, product


def _make_documents() -> list[LegalDocument]:
    labels = {
        LegalDocumentType.DISCLAIMER: "Предупреждение о рисках",
        LegalDocumentType.OFFER: "Публичная оферта",
        LegalDocumentType.PRIVACY_POLICY: "Политика конфиденциальности",
        LegalDocumentType.PAYMENT_CONSENT: "Согласие на оплату",
    }
    return [
        LegalDocument(
            id=f"doc-{item.value}",
            document_type=item,
            version="v1",
            title=labels[item],
            content_md="text",
            source_path=f"legal/{item.value}/v1.md",
            is_active=True,
        )
        for item in labels
    ]


def _make_snapshot(user: User) -> SimpleNamespace:
    return SimpleNamespace(
        user=user,
        has_access=True,
        subscriptions=[],
        active_subscriptions=[],
        payments=[],
        pending_payments=[],
        visible_message_titles=["Покупка SBER"],
    )


def test_root_redirects_to_catalog() -> None:
    with _build_client(FakePublicRepository()) as client:
        response = client.get("/", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/catalog"


def test_miniapp_renders_bootstrap_page() -> None:
    with _build_client(FakePublicRepository()) as client:
        response = client.get("/miniapp")

        assert response.status_code == 200
        assert "Открываем каталог стратегий" in response.text
        assert "Mini App подтверждает ваш Telegram-профиль и сразу открывает витрину стратегий" in response.text


def test_catalog_renders_strategies(monkeypatch) -> None:
    strategy, _product = _make_strategy_and_product()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.list_public_strategies",
        lambda _repository: _async_return([strategy]),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.build_strategy_quote_strip",
        lambda _strategy: _async_return([SimpleNamespace(ticker="NVTK", last_price_text="123.45", change_text="+1.20%")]),
    )

    with _build_client(FakePublicRepository()) as client:
        response = client.get("/catalog")

        assert response.status_code == 200
        assert "Витрина стратегий" in response.text
        assert "Momentum RU" in response.text
        assert "/catalog/strategies/momentum-ru" in response.text
        assert "NVTK · 123.45 · +1.20%" in response.text


def test_app_catalog_shows_miniapp_navigation(monkeypatch) -> None:
    strategy, _product = _make_strategy_and_product()
    user = User(id="user-1", telegram_user_id=12345, username="leaduser", full_name="Lead User", timezone="Europe/Moscow")
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.list_public_strategies",
        lambda _repository: _async_return([strategy]),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.build_strategy_quote_strip",
        lambda _strategy: _async_return([SimpleNamespace(ticker="NVTK", last_price_text="123.45", change_text="+1.20%")]),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.get_subscriber_status_snapshot",
        lambda _repository, telegram_user_id: _async_return(_make_snapshot(user)),
    )

    with _build_client(
        FakePublicRepository(),
        auth_repository=FakeAuthRepository(user),
        access_repository=FakeAccessRepository(),
    ) as client:
        client.cookies.set("pitchcopytrade_session_tg", build_telegram_fallback_cookie_value(user))
        response = client.get("/app/catalog")

        assert response.status_code == 200
        assert "Lead User" in response.text
        assert "/app/catalog" in response.text
        assert "/app/status" in response.text
        assert "/app/help" in response.text
        assert "/app/subscriptions" in response.text
        assert "/app/payments" in response.text
        assert "/tg-webapp/auth" in response.text
        assert "NVTK · 123.45 · +1.20%" in response.text


def test_strategy_detail_renders_products(monkeypatch) -> None:
    strategy, product = _make_strategy_and_product()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.get_public_strategy_by_slug",
        lambda _repository, _slug: _async_return(strategy),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.build_strategy_quote_strip",
        lambda _strategy: _async_return([SimpleNamespace(ticker="NVTK", last_price_text="123.45", change_text="+1.20%")]),
    )

    with _build_client(FakePublicRepository()) as client:
        response = client.get("/catalog/strategies/momentum-ru")

        assert response.status_code == 200
        assert "Momentum RU" in response.text
        assert product.title in response.text
        assert f"/checkout/{product.id}" in response.text
        assert "NVTK · 123.45 · +1.20%" in response.text
        assert "Короткий тезис" in response.text
        assert "Тарифы и CTA" in response.text
        assert "FAQ и документы" in response.text


def test_app_strategy_detail_uses_miniapp_checkout_link(monkeypatch) -> None:
    strategy, product = _make_strategy_and_product()
    user = User(id="user-1", telegram_user_id=12345, username="leaduser", full_name="Lead User", timezone="Europe/Moscow")
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.get_public_strategy_by_slug",
        lambda _repository, _slug: _async_return(strategy),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.get_subscriber_status_snapshot",
        lambda _repository, telegram_user_id: _async_return(_make_snapshot(user)),
    )

    with _build_client(
        FakePublicRepository(),
        auth_repository=FakeAuthRepository(user),
        access_repository=FakeAccessRepository(),
    ) as client:
        client.cookies.set("pitchcopytrade_session_tg", build_telegram_fallback_cookie_value(user))
        response = client.get("/app/strategies/momentum-ru")

        assert response.status_code == 200
        assert f"/app/checkout/{product.id}" in response.text
        assert "Короткий тезис" in response.text
        assert "Выбрать подписку" in response.text


def test_checkout_page_renders_documents(monkeypatch) -> None:
    _strategy, product = _make_strategy_and_product()
    documents = _make_documents()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.get_public_product",
        lambda _repository, _product_id: _async_return(product),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.list_active_checkout_documents",
        lambda _repository: _async_return(documents),
    )

    with _build_client(FakePublicRepository()) as client:
        response = client.get("/checkout/product-1")

        assert response.status_code == 200
        assert "оформление подписки" in response.text
        assert "Momentum RU" in response.text
        assert "Согласие на оплату" in response.text
        assert "/legal/doc-payment_consent" in response.text


def test_app_checkout_prefills_telegram_user(monkeypatch) -> None:
    _strategy, product = _make_strategy_and_product()
    documents = _make_documents()
    user = User(
        id="user-1",
        telegram_user_id=12345,
        username="leaduser",
        full_name="Lead User",
        email="lead@example.com",
        timezone="Europe/Moscow",
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.get_public_product",
        lambda _repository, _product_id: _async_return(product),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.list_active_checkout_documents",
        lambda _repository: _async_return(documents),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.get_subscriber_status_snapshot",
        lambda _repository, telegram_user_id: _async_return(_make_snapshot(user)),
    )

    with _build_client(
        FakePublicRepository(),
        auth_repository=FakeAuthRepository(user),
        access_repository=FakeAccessRepository(),
    ) as client:
        client.cookies.set("pitchcopytrade_session_tg", build_telegram_fallback_cookie_value(user))
        response = client.get("/app/checkout/product-1")

        assert response.status_code == 200
        assert "Lead User" in response.text
        assert "lead@example.com" in response.text
        assert "/app/catalog" in response.text


def test_legal_document_page_reads_local_markdown(monkeypatch) -> None:
    documents = _make_documents()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.list_active_checkout_documents",
        lambda _repository: _async_return(documents),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.read_legal_document_markdown",
        lambda document: f"loaded from {document.source_path}",
    )

    with _build_client(FakePublicRepository()) as client:
        response = client.get("/legal/doc-offer")

        assert response.status_code == 200
        assert "Публичная оферта" in response.text
        assert "loaded from legal/offer/v1.md" in response.text


def test_checkout_submit_creates_stub_flow(monkeypatch) -> None:
    _strategy, product = _make_strategy_and_product()
    documents = _make_documents()
    user = User(id="user-1", email="lead@example.com", full_name="Lead User", timezone="Europe/Moscow")
    payment = Payment(
        id="payment-1",
        user_id="user-1",
        product_id="product-1",
        provider=PaymentProvider.STUB_MANUAL,
        status=PaymentStatus.PENDING,
        amount_rub=499,
        discount_rub=0,
        final_amount_rub=499,
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
    result = SimpleNamespace(user=user, payment=payment, subscription=subscription, required_documents=documents)

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.get_public_product",
        lambda _repository, _product_id: _async_return(product),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.list_active_checkout_documents",
        lambda _repository: _async_return(documents),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.create_stub_checkout",
        lambda _repository, product, request: _async_return(result),
    )

    with _build_client(FakePublicRepository()) as client:
        response = client.post(
            "/checkout/product-1",
            data={
                "full_name": "Lead User",
                "email": "lead@example.com",
                "timezone_name": "Europe/Moscow",
                "lead_source_name": "ads",
                "accepted_document_ids": [item.id for item in documents],
            },
        )

        assert response.status_code == 201
        assert "Заявка создана" in response.text
        assert "MANUAL-MOMENTUM-ABCD1234" in response.text


def test_checkout_submit_handles_paymentless_free_flow(monkeypatch) -> None:
    _strategy, product = _make_strategy_and_product()
    product.price_rub = 0
    documents = _make_documents()
    user = User(id="user-1", email="lead@example.com", full_name="Lead User", timezone="Europe/Moscow")
    subscription = Subscription(
        id="subscription-1",
        user_id="user-1",
        product_id="product-1",
        payment_id=None,
        status=SubscriptionStatus.ACTIVE,
        autorenew_enabled=True,
        is_trial=True,
        manual_discount_rub=0,
        start_at=datetime(2026, 3, 11, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
    )
    result = SimpleNamespace(user=user, payment=None, subscription=subscription, required_documents=documents)

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.get_public_product",
        lambda _repository, _product_id: _async_return(product),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.list_active_checkout_documents",
        lambda _repository: _async_return(documents),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.create_stub_checkout",
        lambda _repository, product, request: _async_return(result),
    )

    with _build_client(FakePublicRepository()) as client:
        response = client.post(
            "/checkout/product-1",
            data={
                "full_name": "Lead User",
                "email": "lead@example.com",
                "timezone_name": "Europe/Moscow",
                "lead_source_name": "ads",
                "accepted_document_ids": [item.id for item in documents],
            },
        )

        assert response.status_code == 201
        assert "Оплата не требуется" in response.text
        assert "Оплатить по СБП" not in response.text


def test_app_checkout_submit_creates_telegram_linked_flow(monkeypatch) -> None:
    _strategy, product = _make_strategy_and_product()
    documents = _make_documents()
    user = User(
        id="user-1",
        telegram_user_id=12345,
        username="leaduser",
        full_name="Lead User",
        email="lead@example.com",
        timezone="Europe/Moscow",
    )
    payment = Payment(
        id="payment-1",
        user_id="user-1",
        product_id="product-1",
        provider=PaymentProvider.STUB_MANUAL,
        status=PaymentStatus.PENDING,
        amount_rub=499,
        discount_rub=0,
        final_amount_rub=499,
        currency="RUB",
        stub_reference="MANUAL-MINIAPP-ABCD1234",
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
    result = SimpleNamespace(user=user, payment=payment, subscription=subscription, required_documents=documents)
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.get_public_product",
        lambda _repository, _product_id: _async_return(product),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.list_active_checkout_documents",
        lambda _repository: _async_return(documents),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.get_subscriber_status_snapshot",
        lambda _repository, telegram_user_id: _async_return(_make_snapshot(user)),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.create_telegram_stub_checkout",
        lambda _repository, **kwargs: _async_return(result),
    )

    with _build_client(
        FakePublicRepository(),
        auth_repository=FakeAuthRepository(user),
        access_repository=FakeAccessRepository(),
    ) as client:
        client.cookies.set("pitchcopytrade_session_tg", build_telegram_fallback_cookie_value(user))
        response = client.post(
            "/app/checkout/product-1",
            data={
                "full_name": "Lead User",
                "email": "lead@example.com",
                "timezone_name": "Europe/Moscow",
                "accepted_document_ids": [item.id for item in documents],
                "promo_code_value": "WELCOME10",
            },
        )

        assert response.status_code == 201
        assert "MANUAL-MINIAPP-ABCD1234" in response.text
        assert "/app/payments" in response.text


def test_app_checkout_submit_handles_paymentless_free_flow(monkeypatch) -> None:
    _strategy, product = _make_strategy_and_product()
    product.price_rub = 0
    documents = _make_documents()
    user = User(
        id="user-1",
        telegram_user_id=12345,
        username="leaduser",
        full_name="Lead User",
        email="lead@example.com",
        timezone="Europe/Moscow",
    )
    subscription = Subscription(
        id="subscription-1",
        user_id="user-1",
        product_id="product-1",
        payment_id=None,
        status=SubscriptionStatus.ACTIVE,
        autorenew_enabled=True,
        is_trial=True,
        manual_discount_rub=0,
        start_at=datetime(2026, 3, 11, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
    )
    result = SimpleNamespace(user=user, payment=None, subscription=subscription, required_documents=documents)
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.get_public_product",
        lambda _repository, _product_id: _async_return(product),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.list_active_checkout_documents",
        lambda _repository: _async_return(documents),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.get_subscriber_status_snapshot",
        lambda _repository, telegram_user_id: _async_return(_make_snapshot(user)),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.create_telegram_stub_checkout",
        lambda _repository, **kwargs: _async_return(result),
    )

    with _build_client(
        FakePublicRepository(),
        auth_repository=FakeAuthRepository(user),
        access_repository=FakeAccessRepository(),
    ) as client:
        client.cookies.set("pitchcopytrade_session_tg", build_telegram_fallback_cookie_value(user))
        response = client.post(
            "/app/checkout/product-1",
            data={
                "full_name": "Lead User",
                "email": "lead@example.com",
                "timezone_name": "Europe/Moscow",
                "accepted_document_ids": [item.id for item in documents],
                "promo_code_value": "",
            },
        )

        assert response.status_code == 201
        assert "Оплата не требуется" in response.text
        assert "/app/subscriptions" in response.text


def test_checkout_submit_renders_applied_promo(monkeypatch) -> None:
    _strategy, product = _make_strategy_and_product()
    documents = _make_documents()
    promo_code = PromoCode(
        id="promo-1",
        code="WELCOME10",
        description="Welcome",
        discount_percent=10,
        is_active=True,
        max_redemptions=0,
        current_redemptions=0,
    )
    user = User(id="user-1", email="lead@example.com", full_name="Lead User", timezone="Europe/Moscow")
    payment = Payment(
        id="payment-1",
        user_id="user-1",
        product_id="product-1",
        provider=PaymentProvider.STUB_MANUAL,
        status=PaymentStatus.PENDING,
        amount_rub=499,
        discount_rub=49,
        final_amount_rub=450,
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
    result = SimpleNamespace(
        user=user,
        payment=payment,
        subscription=subscription,
        required_documents=documents,
        applied_promo_code=promo_code,
    )

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.get_public_product",
        lambda _repository, _product_id: _async_return(product),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.list_active_checkout_documents",
        lambda _repository: _async_return(documents),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.create_stub_checkout",
        lambda _repository, product, request: _async_return(result),
    )

    with _build_client(FakePublicRepository()) as client:
        response = client.post(
            "/checkout/product-1",
            data={
                "full_name": "Lead User",
                "email": "lead@example.com",
                "timezone_name": "Europe/Moscow",
                "lead_source_name": "ads",
                "promo_code_value": "WELCOME10",
                "accepted_document_ids": [item.id for item in documents],
            },
        )

        assert response.status_code == 201
        assert "WELCOME10" in response.text
        assert "450 руб" in response.text


def test_tbank_callback_endpoint_validates_token_and_returns_ok(monkeypatch) -> None:
    with _build_client(FakePublicRepository()) as client:
        payload = {"OrderId": "payment-1", "Status": "CONFIRMED", "Success": True}
        monkeypatch.setattr(TBankAcquiringClient, "validate_callback_token", lambda self, data: True)
        monkeypatch.setattr(
            "pitchcopytrade.api.routes.public.process_tbank_callback",
            lambda session, payload: _async_return(None),
        )

        response = client.post("/payments/tbank/notify", json=payload)

        assert response.status_code == 200
        assert response.text == "OK"


async def _async_return(value):
    return value
