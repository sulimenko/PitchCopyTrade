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


class _TitleGuardProduct:
    def __init__(self, *, product_id: str = "product-1", title: str = "Momentum RU") -> None:
        self.id = product_id
        self._title = title
        self.title_accesses = 0

    @property
    def title(self) -> str:
        self.title_accesses += 1
        if self.title_accesses > 2:
            raise AssertionError("product.title accessed too many times")
        return self._title


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


def test_app_renders_bootstrap_page() -> None:
    with _build_client(FakePublicRepository()) as client:
        response = client.get("/app?entry=bot_start")

        assert response.status_code == 200
        assert "Запустите Mini App из бота" in response.text
        assert "Открыть бота" in response.text
        assert "pct_journey_id=" in response.headers["set-cookie"]


def test_miniapp_root_renders_entry_page() -> None:
    with _build_client(FakePublicRepository()) as client:
        response = client.get("/miniapp")

        assert response.status_code == 200
        assert "Запустите Mini App из бота" in response.text
        assert "Открыть бота" in response.text
        assert "pct_journey_id=" in response.headers["set-cookie"]


def test_miniapp_root_redirects_to_catalog_with_telegram_cookie() -> None:
    user = User(id="user-1", telegram_user_id=12345, full_name="Lead User")
    repository = FakePublicRepository()
    auth_repository = FakeAuthRepository(user)
    with _build_client(repository, auth_repository=auth_repository) as client:
        client.cookies.set("pitchcopytrade_session_tg", build_telegram_fallback_cookie_value(user))
        response = client.get("/miniapp", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/app/catalog"


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
        assert "/catalog/strategies/momentum-ru?entry=public_catalog" in response.text
        assert "/checkout/momentum-ru-month?entry=public_catalog" in response.text
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
        assert f"/app/strategies/{strategy.slug}?entry=bot_start" in response.text
        assert f"/app/checkout/{strategy.subscription_products[0].slug}?entry=bot_start" in response.text
        assert f'href="/checkout/{strategy.subscription_products[0].slug}"' not in response.text
        assert "pct_journey_id=" in response.headers["set-cookie"]


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
        assert f"/checkout/{product.slug}?entry=public_strategy" in response.text
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
        assert f"/app/checkout/{product.slug}?entry=bot_start" in response.text
        assert f'href="/checkout/{product.slug}"' not in response.text
        assert "Короткий тезис" in response.text
        assert "Выбрать подписку" in response.text


def test_public_checkout_tracing_chain_logs_entry_markers(monkeypatch, capsys) -> None:
    strategy, product = _make_strategy_and_product()
    documents = _make_documents()
    result = SimpleNamespace(
        user=User(id="user-1", email="lead@example.com", full_name="Lead User", timezone="Europe/Moscow"),
        payment=None,
        subscription=Subscription(
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
        ),
        required_documents=documents,
    )

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.list_public_strategies",
        lambda _repository: _async_return([strategy]),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.build_strategy_quote_strip",
        lambda _strategy: _async_return([SimpleNamespace(ticker="NVTK", last_price_text="123.45", change_text="+1.20%")]),
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
        lambda _repository, **kwargs: _async_return(result),
    )

    with _build_client(FakePublicRepository()) as client:
        catalog_response = client.get("/catalog?entry=public_catalog")
        journey_cookie = catalog_response.headers["set-cookie"]
        journey_id = journey_cookie.split("pct_journey_id=")[1].split(";", 1)[0]
        client.cookies.set("pct_journey_id", journey_id)

        checkout_response = client.get("/checkout/momentum-ru-month?entry=public_catalog")
        assert f"/catalog/strategies/{strategy.slug}?entry=public_catalog" in catalog_response.text
        assert f"/checkout/{product.slug}?entry=public_catalog" in catalog_response.text
        assert 'name="entry_id" value="' in checkout_response.text
        assert 'name="entry_surface" value="public"' in checkout_response.text

        response = client.post(
            "/checkout/momentum-ru-month?entry=public_catalog",
            data={
                "full_name": "Lead User",
                "email": "lead@example.com",
                "timezone_name": "Europe/Moscow",
                "lead_source_name": "ads",
                "accepted_document_ids": [item.id for item in documents],
                "entry_id": journey_id,
                "entry_surface": "public",
            },
        )

    captured = capsys.readouterr()
    assert response.status_code == 201
    assert 'name="entry_surface" value="public"' in checkout_response.text


def test_app_checkout_tracing_chain_logs_entry_markers(monkeypatch, capsys) -> None:
    strategy, product = _make_strategy_and_product()
    documents = _make_documents()
    user = User(id="user-1", telegram_user_id=12345, username="leaduser", full_name="Lead User", timezone="Europe/Moscow")
    result = SimpleNamespace(
        user=user,
        payment=None,
        subscription=Subscription(
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
        ),
        required_documents=documents,
    )

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.list_public_strategies",
        lambda _repository: _async_return([strategy]),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.build_strategy_quote_strip",
        lambda _strategy: _async_return([SimpleNamespace(ticker="NVTK", last_price_text="123.45", change_text="+1.20%")]),
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
        catalog_response = client.get("/app/catalog?entry=miniapp_catalog")
        journey_cookie = catalog_response.headers["set-cookie"]
        journey_id = journey_cookie.split("pct_journey_id=")[1].split(";", 1)[0]
        client.cookies.set("pct_journey_id", journey_id)

        checkout_response = client.get("/app/checkout/momentum-ru-month?entry=miniapp_catalog")
        assert f"/app/strategies/{strategy.slug}?entry=miniapp_catalog" in catalog_response.text
        assert f"/app/checkout/{product.slug}?entry=miniapp_catalog" in catalog_response.text
        assert 'name="entry_id" value="' in checkout_response.text
        assert 'name="entry_surface" value="miniapp"' in checkout_response.text

        response = client.post(
            "/app/checkout/momentum-ru-month?entry=miniapp_catalog",
            data={
                "full_name": "Lead User",
                "email": "lead@example.com",
                "timezone_name": "Europe/Moscow",
                "accepted_document_ids": [item.id for item in documents],
                "promo_code_value": "",
                "entry_id": journey_id,
                "entry_surface": "miniapp",
            },
        )

    captured = capsys.readouterr()
    assert response.status_code == 201
    assert 'name="entry_surface" value="miniapp"' in checkout_response.text


def test_app_checkout_submit_logs_controlled_invalid_request(monkeypatch, capsys) -> None:
    strategy, product = _make_strategy_and_product()
    documents = _make_documents()
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

    async def fail_checkout(*_args, **_kwargs):
        raise ValueError("Нужно принять все обязательные документы перед оплатой")

    monkeypatch.setattr("pitchcopytrade.api.routes.app.create_telegram_stub_checkout", fail_checkout)

    with _build_client(
        FakePublicRepository(),
        auth_repository=FakeAuthRepository(user),
        access_repository=FakeAccessRepository(),
    ) as client:
        client.cookies.set("pitchcopytrade_session_tg", build_telegram_fallback_cookie_value(user))
        catalog_response = client.get("/app/catalog?entry=miniapp_catalog")
        journey_cookie = catalog_response.headers["set-cookie"]
        journey_id = journey_cookie.split("pct_journey_id=")[1].split(";", 1)[0]
        client.cookies.set("pct_journey_id", journey_id)

        response = client.post(
            "/app/checkout/momentum-ru-month?entry=miniapp_catalog",
            data={
                "full_name": "Lead User",
                "email": "lead@example.com",
                "timezone_name": "Europe/Moscow",
                "promo_code_value": "",
                "entry_id": journey_id,
                "entry_surface": "miniapp",
            },
        )

    captured = capsys.readouterr()
    assert response.status_code == 422
    assert "Нужно принять все обязательные документы перед оплатой" in response.text


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
        response = client.get("/checkout/momentum-ru-month")

        assert response.status_code == 200
        assert "оформление подписки" in response.text
        assert "Momentum RU" in response.text
        assert "Согласие на оплату" in response.text
        assert "/legal/doc-payment_consent" in response.text
        assert 'name="timezone_name"' in response.text
        assert 'name="lead_source_name"' in response.text
        assert 'name="accepted_document_ids"' in response.text
        assert 'name="entry_id" value="' in response.text
        assert 'name="entry_surface" value="public"' in response.text


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
        response = client.get("/app/checkout/momentum-ru-month")

        assert response.status_code == 200
        assert "Lead User" in response.text
        assert "lead@example.com" in response.text
        assert "/app/catalog" in response.text
        assert 'name="timezone_name"' in response.text
        assert 'name="lead_source_name"' in response.text
        assert 'name="accepted_document_ids"' in response.text
        assert 'name="entry_id" value="' in response.text
        assert 'name="entry_surface" value="miniapp"' in response.text


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
            "/checkout/momentum-ru-month",
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


def test_checkout_submit_links_cookie_telegram_user_id(monkeypatch) -> None:
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
    captured = {}
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

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.get_public_product",
        lambda _repository, _product_id: _async_return(product),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.list_active_checkout_documents",
        lambda _repository: _async_return(documents),
    )

    async def capture_checkout(_repository, product, request):
        captured["request"] = request
        return SimpleNamespace(user=user, payment=None, subscription=subscription, required_documents=documents)

    monkeypatch.setattr("pitchcopytrade.api.routes.public.create_stub_checkout", capture_checkout)

    with _build_client(
        FakePublicRepository(),
        auth_repository=FakeAuthRepository(user),
        access_repository=FakeAccessRepository(),
    ) as client:
        client.cookies.set("pitchcopytrade_session_tg", build_telegram_fallback_cookie_value(user))
        response = client.post(
            "/checkout/momentum-ru-month",
            data={
                "full_name": "Lead User",
                "email": "lead@example.com",
                "timezone_name": "Europe/Moscow",
                "lead_source_name": "ads",
                "accepted_document_ids": [item.id for item in documents],
            },
        )

        assert response.status_code == 201
        assert captured["request"].telegram_user_id == 12345


def test_checkout_submit_redirects_telegram_intended_flow_without_context(monkeypatch, capsys) -> None:
    _strategy, product = _make_strategy_and_product()
    documents = _make_documents()
    create_stub_called = False

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.get_public_product",
        lambda _repository, _product_id: _async_return(product),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.public.list_active_checkout_documents",
        lambda _repository: _async_return(documents),
    )

    async def fail_if_called(*_args, **_kwargs):
        nonlocal create_stub_called
        create_stub_called = True
        raise AssertionError("create_stub_checkout should not be called for telegram-intended public checkout without context")

    monkeypatch.setattr("pitchcopytrade.api.routes.public.create_stub_checkout", fail_if_called)

    with _build_client(FakePublicRepository()) as client:
        response = client.post(
            "/checkout/momentum-ru-month",
            data={
                "full_name": "Lead User",
                "email": "lead@example.com",
                "timezone_name": "Europe/Moscow",
                "lead_source_name": "telegram_miniapp",
                "accepted_document_ids": [item.id for item in documents],
            },
            follow_redirects=False,
        )

    captured = capsys.readouterr()
    assert response.status_code == 303
    assert response.headers["location"] == "/verify/telegram?next=/app/catalog&requested_next=/checkout/momentum-ru-month"
    assert create_stub_called is False
    assert "Public checkout route path=/checkout/momentum-ru-month" in captured.out
    assert "lead_source=telegram_miniapp" in captured.out
    assert "telegram_cookie_present=False" in captured.out
    assert "auth_telegram_user_id=None" in captured.out
    assert "pct_journey_id=" in response.headers["set-cookie"]


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
            "/checkout/momentum-ru-month",
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
            "/app/checkout/momentum-ru-month",
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


def test_app_checkout_submit_rejects_missing_telegram_id(monkeypatch) -> None:
    _strategy, _product = _make_strategy_and_product()
    documents = _make_documents()
    user = User(
        id="user-1",
        telegram_user_id=None,
        username="leaduser",
        full_name="Lead User",
        email="lead@example.com",
        timezone="Europe/Moscow",
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.get_public_product",
        lambda _repository, _product_id: _async_return(_product),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.list_active_checkout_documents",
        lambda _repository: _async_return(documents),
    )

    with _build_client(
        FakePublicRepository(),
        auth_repository=FakeAuthRepository(user),
        access_repository=FakeAccessRepository(),
    ) as client:
        client.cookies.set("pitchcopytrade_session_tg", build_telegram_fallback_cookie_value(user))
        response = client.post(
            "/app/checkout/momentum-ru-month",
            data={
                "full_name": "Lead User",
                "email": "lead@example.com",
                "timezone_name": "Europe/Moscow",
                "accepted_document_ids": [item.id for item in documents],
                "promo_code_value": "",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/verify/telegram?next=/app/catalog&requested_next=/app/checkout/momentum-ru-month"


def test_app_subscription_renew_redirects_missing_telegram_id() -> None:
    user = User(id="user-1", telegram_user_id=None, username="leaduser", full_name="Lead User", timezone="Europe/Moscow")

    with _build_client(
        FakePublicRepository(),
        auth_repository=FakeAuthRepository(user),
        access_repository=FakeAccessRepository(),
    ) as client:
        client.cookies.set("pitchcopytrade_session_tg", build_telegram_fallback_cookie_value(user))
        response = client.post("/app/subscriptions/sub-1/renew", data={"promo_code_value": ""}, follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/verify/telegram?next=/app/catalog&requested_next=/app/subscriptions/sub-1/renew"


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
            "/app/checkout/momentum-ru-month",
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
            "/checkout/momentum-ru-month",
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


def test_checkout_submit_uses_saved_product_title_on_exception(monkeypatch) -> None:
    product = _TitleGuardProduct()
    documents = _make_documents()

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
        lambda _repository, product, request: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    with _build_client(FakePublicRepository()) as client:
        response = client.post(
            "/checkout/momentum-ru-month",
            data={
                "full_name": "Lead User",
                "email": "lead@example.com",
                "timezone_name": "Europe/Moscow",
                "lead_source_name": "ads",
                "accepted_document_ids": [item.id for item in documents],
            },
        )

        assert response.status_code == 503
        assert "Подписка Momentum RU" in response.text
        assert product.title_accesses == 2


def test_app_checkout_submit_uses_saved_product_title_on_exception(monkeypatch) -> None:
    product = _TitleGuardProduct()
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
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.app.create_telegram_stub_checkout",
        lambda _repository, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    with _build_client(
        FakePublicRepository(),
        auth_repository=FakeAuthRepository(user),
        access_repository=FakeAccessRepository(),
    ) as client:
        client.cookies.set("pitchcopytrade_session_tg", build_telegram_fallback_cookie_value(user))
        response = client.post(
            "/app/checkout/momentum-ru-month",
            data={
                "full_name": "Lead User",
                "email": "lead@example.com",
                "timezone_name": "Europe/Moscow",
                "accepted_document_ids": [item.id for item in documents],
                "promo_code_value": "",
            },
        )

        assert response.status_code == 503
        assert "Подписка Momentum RU" in response.text
        assert product.title_accesses == 2


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
