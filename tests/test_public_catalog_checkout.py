from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from pitchcopytrade.api.deps.repositories import get_access_repository, get_auth_repository, get_public_repository
from pitchcopytrade.api.main import create_app
from pitchcopytrade.auth.session import build_telegram_fallback_cookie_value
from pitchcopytrade.payments.tbank import TBankAcquiringClient
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
        title="Momentum RU Monthly",
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


def test_root_redirects_to_catalog() -> None:
    with _build_client(FakePublicRepository()) as client:
        response = client.get("/", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/catalog"


def test_miniapp_redirects_to_catalog_surface() -> None:
    with _build_client(FakePublicRepository()) as client:
        response = client.get("/miniapp", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/catalog?surface=miniapp"


def test_catalog_renders_strategies(monkeypatch) -> None:
    strategy, _product = _make_strategy_and_product()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.list_public_strategies",
        lambda _session: _async_return([strategy]),
    )

    with _build_client(FakePublicRepository()) as client:
        response = client.get("/catalog")

        assert response.status_code == 200
        assert "Витрина стратегий" in response.text
        assert "Momentum RU" in response.text
        assert "/catalog/strategies/momentum-ru" in response.text


def test_catalog_miniapp_shows_subscriber_overview_when_cookie_exists(monkeypatch) -> None:
    strategy, _product = _make_strategy_and_product()
    user = User(id="user-1", telegram_user_id=12345, username="leaduser", full_name="Lead User", timezone="Europe/Moscow")
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.list_public_strategies",
        lambda _session: _async_return([strategy]),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.get_subscriber_status_snapshot",
        lambda _repository, telegram_user_id: _async_return(
            SimpleNamespace(
                user=user,
                has_access=True,
                active_subscriptions=[SimpleNamespace()],
                pending_payments=[SimpleNamespace()],
                visible_recommendation_titles=["Покупка SBER"],
            )
        ),
    )

    with _build_client(
        FakePublicRepository(),
        auth_repository=FakeAuthRepository(user),
        access_repository=FakeAccessRepository(),
    ) as client:
        client.cookies.set("pitchcopytrade_session_tg", build_telegram_fallback_cookie_value(user))
        response = client.get("/catalog?surface=miniapp")

        assert response.status_code == 200
        assert "мой профиль" in response.text
        assert "Lead User" in response.text
        assert "/app/status" in response.text


def test_strategy_detail_renders_products(monkeypatch) -> None:
    strategy, product = _make_strategy_and_product()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.get_public_strategy_by_slug",
        lambda _session, _slug: _async_return(strategy),
    )

    with _build_client(FakePublicRepository()) as client:
        response = client.get("/catalog/strategies/momentum-ru")

        assert response.status_code == 200
        assert "Momentum RU" in response.text
        assert product.title in response.text
        assert f"/checkout/{product.id}" in response.text


def test_checkout_page_renders_documents(monkeypatch) -> None:
    _strategy, product = _make_strategy_and_product()
    documents = _make_documents()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.get_public_product",
        lambda _session, _product_id: _async_return(product),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.list_active_checkout_documents",
        lambda _session: _async_return(documents),
    )

    with _build_client(FakePublicRepository()) as client:
        response = client.get("/checkout/product-1")

        assert response.status_code == 200
        assert "оформление подписки" in response.text
        assert "Momentum RU Monthly" in response.text
        assert "Согласие на оплату" in response.text
        assert '/legal/doc-payment_consent' in response.text


def test_legal_document_page_reads_local_markdown(monkeypatch) -> None:
    documents = _make_documents()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.list_active_checkout_documents",
        lambda _session: _async_return(documents),
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
    result = SimpleNamespace(user=user, payment=payment, subscription=subscription, required_documents=documents)

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.get_public_product",
        lambda _session, _product_id: _async_return(product),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.list_active_checkout_documents",
        lambda _session: _async_return(documents),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.create_stub_checkout",
        lambda _session, product, request: _async_return(result),
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


def test_checkout_submit_renders_applied_promo(monkeypatch) -> None:
    _strategy, product = _make_strategy_and_product()
    documents = _make_documents()
    promo_code = PromoCode(
        id="promo-1",
        code="WELCOME10",
        description="Launch promo",
        discount_percent=10,
        current_redemptions=0,
        is_active=True,
    )
    user = User(id="user-1", email="lead@example.com", full_name="Lead User", timezone="Europe/Moscow")
    payment = Payment(
        id="payment-1",
        user_id="user-1",
        product_id="product-1",
        promo_code_id="promo-1",
        provider=PaymentProvider.STUB_MANUAL,
        status=PaymentStatus.PENDING,
        amount_rub=4900,
        discount_rub=490,
        final_amount_rub=4410,
        currency="RUB",
        stub_reference="MANUAL-MOMENTUM-PROMO",
    )
    payment.promo_code = promo_code
    subscription = Subscription(
        id="subscription-1",
        user_id="user-1",
        product_id="product-1",
        payment_id="payment-1",
        applied_promo_code_id="promo-1",
        status=SubscriptionStatus.PENDING,
        autorenew_enabled=True,
        is_trial=True,
        manual_discount_rub=0,
        start_at=datetime(2026, 3, 11, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
    )
    subscription.applied_promo_code = promo_code
    result = SimpleNamespace(
        user=user,
        payment=payment,
        subscription=subscription,
        required_documents=documents,
        applied_promo_code=promo_code,
    )

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.get_public_product",
        lambda _session, _product_id: _async_return(product),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.list_active_checkout_documents",
        lambda _session: _async_return(documents),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.create_stub_checkout",
        lambda _session, product, request: _async_return(result),
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
        assert "скидка 490 руб" in response.text


def test_tbank_notify_accepts_valid_callback(monkeypatch) -> None:
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "payments": type(
                    "Payments",
                    (),
                    {
                        "tinkoff_terminal_key": type("Secret", (), {"get_secret_value": lambda self: "term"})(),
                        "tinkoff_secret_key": type("Secret", (), {"get_secret_value": lambda self: "secret"})(),
                    },
                )()
            },
        )(),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.process_tbank_callback",
        lambda _session, payload: _async_return(SimpleNamespace(found=True, changed=True, payment_status="paid")),
    )

    payload = {"TerminalKey": "term", "PaymentId": "777", "Status": "CONFIRMED"}
    payload["Token"] = TBankAcquiringClient._build_token(payload, password="secret")

    with _build_client(FakePublicRepository()) as client:
        response = client.post("/payments/tbank/notify", json=payload)

        assert response.status_code == 200
        assert response.text == "OK"


async def _async_return(value):
    return value
