from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient

from pitchcopytrade.api.main import create_app
from pitchcopytrade.api.deps.auth import require_admin
from pitchcopytrade.services import admin as admin_service
from pitchcopytrade.core.config import reset_settings_cache
from pitchcopytrade.db.session import get_optional_db_session
from pitchcopytrade.auth.passwords import hash_password
from pitchcopytrade.db.models.accounts import AuthorProfile, Role, User
from pitchcopytrade.db.models.catalog import Bundle, Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import Payment, PromoCode, Subscription, UserConsent
from pitchcopytrade.db.models.content import Recommendation
from pitchcopytrade.db.models.commerce import LegalDocument
from pitchcopytrade.db.models.enums import (
    BillingPeriod,
    LegalDocumentType,
    PaymentProvider,
    PaymentStatus,
    ProductType,
    RecommendationKind,
    RecommendationStatus,
    RiskLevel,
    RoleSlug,
    StrategyStatus,
    SubscriptionStatus,
    UserStatus,
)


class FakeAsyncSession:
    def __init__(self) -> None:
        self.users_by_id: dict[str, User] = {}

    async def execute(self, query: Any):
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))

        class Result:
            def __init__(self, user: User | None) -> None:
                self._user = user

            def scalar_one_or_none(self) -> User | None:
                return self._user

        for user_id, user in self.users_by_id.items():
            if f"'{user_id}'" in compiled:
                return Result(user)

        return Result(None)


def _make_admin_user() -> User:
    user = User(
        id="admin-1",
        username="admin",
        email="admin@example.com",
        full_name="Admin User",
        password_hash=hash_password("test-pass"),
        timezone="Europe/Moscow",
        status=UserStatus.ACTIVE,
    )
    user.roles = [Role(slug=RoleSlug.ADMIN, title="Admin")]
    return user


def _make_author(author_id: str, user_id: str, display_name: str) -> AuthorProfile:
    author_user = User(
        id=user_id,
        username=display_name.lower().replace(" ", "_"),
        email=f"{user_id}@example.com",
        full_name=display_name,
        timezone="Europe/Moscow",
    )
    profile = AuthorProfile(
        id=author_id,
        user_id=user_id,
        display_name=display_name,
        slug=display_name.lower().replace(" ", "-"),
        is_active=True,
    )
    profile.user = author_user
    return profile


def _make_strategy(strategy_id: str, author: AuthorProfile, title: str) -> Strategy:
    strategy = Strategy(
        id=strategy_id,
        author_id=author.id,
        slug=title.lower().replace(" ", "-"),
        title=title,
        short_description=f"{title} short",
        full_description=f"{title} full",
        risk_level=RiskLevel.MEDIUM,
        status=StrategyStatus.PUBLISHED,
        min_capital_rub=150000,
        is_public=True,
    )
    strategy.author = author
    return strategy


def _make_bundle(bundle_id: str, title: str) -> Bundle:
    return Bundle(
        id=bundle_id,
        slug=title.lower().replace(" ", "-"),
        title=title,
        description=f"{title} bundle",
        is_public=True,
        is_active=True,
    )


def _make_product(product_id: str, strategy: Strategy) -> SubscriptionProduct:
    product = SubscriptionProduct(
        id=product_id,
        product_type=ProductType.STRATEGY,
        slug="momentum-ru-month",
        title="Momentum RU Monthly",
        description="Подписка на стратегию",
        strategy_id=strategy.id,
        author_id=None,
        bundle_id=None,
        billing_period=BillingPeriod.MONTH,
        price_rub=4900,
        trial_days=7,
        is_active=True,
        autorenew_allowed=True,
    )
    product.strategy = strategy
    return product


def _make_payment(payment_id: str, product: SubscriptionProduct) -> Payment:
    user = User(id="lead-1", email="lead@example.com", full_name="Lead User", timezone="Europe/Moscow")
    payment = Payment(
        id=payment_id,
        user_id=user.id,
        product_id=product.id,
        provider=PaymentProvider.STUB_MANUAL,
        status=PaymentStatus.PENDING,
        amount_rub=product.price_rub,
        discount_rub=0,
        final_amount_rub=product.price_rub,
        currency="RUB",
        stub_reference="MANUAL-MOMENTUM-ABCD1234",
    )
    payment.user = user
    payment.product = product
    subscription = Subscription(
        id="subscription-1",
        user_id=user.id,
        product_id=product.id,
        payment_id=payment.id,
        status=SubscriptionStatus.PENDING,
        autorenew_enabled=True,
        is_trial=True,
        manual_discount_rub=0,
        start_at=datetime(2026, 3, 11, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
    )
    subscription.user = user
    subscription.product = product
    document = LegalDocument(
        id="doc-1",
        document_type=LegalDocumentType.OFFER,
        version="v1",
        title="Оферта v1",
        content_md="text",
        is_active=True,
    )
    consent = UserConsent(
        id="consent-1",
        user_id=user.id,
        document_id=document.id,
        payment_id=payment.id,
        accepted_at=datetime(2026, 3, 11, tzinfo=timezone.utc),
        source="checkout",
    )
    consent.document = document
    payment.subscriptions = [subscription]
    payment.consents = [consent]
    return payment


def _make_subscription(subscription_id: str, product: SubscriptionProduct) -> Subscription:
    payment = _make_payment("payment-linked", product)
    subscription = payment.subscriptions[0]
    subscription.id = subscription_id
    subscription.payment = payment
    subscription.payment_id = payment.id
    return subscription


def _make_legal_document(document_id: str, document_type: LegalDocumentType) -> LegalDocument:
    titles = {
        LegalDocumentType.DISCLAIMER: "Предупреждение о рисках",
        LegalDocumentType.OFFER: "Публичная оферта",
        LegalDocumentType.PRIVACY_POLICY: "Политика конфиденциальности",
        LegalDocumentType.PAYMENT_CONSENT: "Согласие на оплату",
    }
    document = LegalDocument(
        id=document_id,
        document_type=document_type,
        version="v1",
        title=titles[document_type],
        content_md="seed markdown",
        source_path=f"legal/{document_type.value}/v1.md",
        is_active=document_type is LegalDocumentType.OFFER,
    )
    document.consents = []
    return document


def _make_promo_code(promo_code_id: str, code: str) -> PromoCode:
    promo_code = PromoCode(
        id=promo_code_id,
        code=code,
        description="Welcome promo",
        discount_percent=10,
        discount_amount_rub=None,
        max_redemptions=100,
        current_redemptions=3,
        is_active=True,
    )
    promo_code.payments = []
    promo_code.subscriptions = []
    return promo_code


def _make_published_recommendation(recommendation_id: str, strategy: Strategy, author: AuthorProfile) -> Recommendation:
    recommendation = Recommendation(
        id=recommendation_id,
        strategy_id=strategy.id,
        author_id=author.id,
        kind=RecommendationKind.NEW_IDEA,
        status=RecommendationStatus.PUBLISHED,
        title="Покупка SBER",
        summary="Сильный спрос",
        published_at=datetime(2026, 3, 11, tzinfo=timezone.utc),
    )
    recommendation.strategy = strategy
    recommendation.author = author
    recommendation.attachments = []
    recommendation.legs = []
    return recommendation


def _build_client(session: FakeAsyncSession, admin_user: User) -> TestClient:
    app = create_app()

    async def override_db_session():
        yield session

    async def override_admin_user():
        return admin_user

    app.dependency_overrides[get_optional_db_session] = override_db_session
    app.dependency_overrides[require_admin] = override_admin_user
    return TestClient(app)


def test_admin_dashboard_renders(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    strategy = _make_strategy("strategy-1", author, "Momentum RU")
    product = _make_product("product-1", strategy)
    payment = _make_payment("payment-1", product)
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.get_admin_dashboard_stats",
        lambda _session: _async_return(
            SimpleNamespace(
                authors_total=3,
                strategies_total=7,
                strategies_public=5,
                active_subscriptions=14,
                recommendations_live=9,
            )
        ),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_strategies",
        lambda _session: _async_return([strategy]),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_products",
        lambda _session: _async_return([product]),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_payments",
        lambda _session: _async_return([payment]),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_subscriptions",
        lambda _session: _async_return(payment.subscriptions),
    )

    with _build_client(session, admin) as client:
        response = client.get("/admin/dashboard")

        assert response.status_code == 200
        assert "Операционный центр" in response.text
        assert "Momentum RU" in response.text
        assert "14" in response.text
        assert "Momentum RU Monthly" in response.text
        assert "Lead User" in response.text


def test_staff_shell_includes_local_ag_grid_vendor_assets(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.get_admin_dashboard_stats",
        lambda _session: _async_return(
            SimpleNamespace(
                authors_total=0,
                strategies_total=0,
                strategies_public=0,
                active_subscriptions=0,
                recommendations_live=0,
            )
        ),
    )
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_strategies", lambda _session: _async_return([]))
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_products", lambda _session: _async_return([]))
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_payments", lambda _session: _async_return([]))
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_subscriptions", lambda _session, query_text='': _async_return([]))

    with _build_client(session, admin) as client:
        response = client.get("/admin/dashboard")

        assert response.status_code == 200
        assert "/static/vendor/ag-grid-community/ag-grid-community.min.noStyle.js" in response.text
        assert "/static/staff/ag-grid-bootstrap.js" in response.text


def test_local_ag_grid_vendor_asset_is_served() -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    session.users_by_id[admin.id] = admin

    with _build_client(session, admin) as client:
        response = client.get("/static/vendor/ag-grid-community/ag-grid-community.min.noStyle.js")

        assert response.status_code == 200
        assert "ag-Grid" in response.text


def test_subscription_list_renders(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    strategy = _make_strategy("strategy-1", author, "Momentum RU")
    product = _make_product("product-1", strategy)
    subscription = _make_subscription("subscription-1", product)
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_subscriptions",
        lambda _session, query_text="": _async_return([subscription]),
    )

    with _build_client(session, admin) as client:
        response = client.get("/admin/subscriptions")

        assert response.status_code == 200
        assert "Подписки и доступ" in response.text
        assert "Lead User" in response.text
        assert "Momentum RU Monthly" in response.text
        assert "/admin/subscriptions/subscription-1" in response.text


def test_subscription_detail_renders(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    strategy = _make_strategy("strategy-1", author, "Momentum RU")
    product = _make_product("product-1", strategy)
    subscription = _make_subscription("subscription-1", product)
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.get_admin_subscription",
        lambda _session, _subscription_id: _async_return(subscription),
    )

    with _build_client(session, admin) as client:
        response = client.get("/admin/subscriptions/subscription-1")

        assert response.status_code == 200
        assert "Карточка подписки" in response.text
        assert "Lead User" in response.text
        assert "Momentum RU Monthly" in response.text
        assert "Доступ к стратегии" in response.text


def test_legal_document_list_renders(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    document = _make_legal_document("doc-offer", LegalDocumentType.OFFER)
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_legal_documents",
        lambda _session: _async_return([document]),
    )

    with _build_client(session, admin) as client:
        response = client.get("/admin/legal")

        assert response.status_code == 200
        assert "Юридические документы" in response.text
        assert "Публичная оферта" in response.text
        assert "/admin/legal/doc-offer/edit" in response.text


def test_legal_document_create_redirects_to_editor(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    session.users_by_id[admin.id] = admin

    async def fake_create(_session, data):
        document = _make_legal_document("doc-new", data.document_type)
        document.version = data.version
        document.title = data.title
        document.content_md = data.content_md
        document.source_path = f"legal/{data.document_type.value}/{data.version}.md"
        return document

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_legal_documents",
        lambda _session: _async_return([]),
    )
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.create_admin_legal_document", fake_create)

    with _build_client(session, admin) as client:
        response = client.post(
            "/admin/legal",
            data={
                "document_type": "offer",
                "version": "v2",
                "title": "offer v2",
                "content_md": "# offer\nbody",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/legal/doc-new/edit"


def test_legal_document_activate_redirects(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    document = _make_legal_document("doc-privacy", LegalDocumentType.PRIVACY_POLICY)
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.get_admin_legal_document",
        lambda _session, _document_id: _async_return(document),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.activate_admin_legal_document",
        lambda _session, _document: _async_return(document),
    )

    with _build_client(session, admin) as client:
        response = client.post("/admin/legal/doc-privacy/activate", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/legal/doc-privacy/edit"


def test_delivery_list_renders(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    strategy = _make_strategy("strategy-1", author, "Momentum RU")
    recommendation = _make_published_recommendation("rec-1", strategy, author)
    session.users_by_id[admin.id] = admin
    record = SimpleNamespace(
        recommendation=recommendation,
        events=[],
        latest_delivery_event=None,
        delivery_attempts=1,
        delivered_recipients=3,
    )

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_delivery_records",
        lambda _session: _async_return([record]),
    )

    with _build_client(session, admin) as client:
        response = client.get("/admin/delivery")

        assert response.status_code == 200
        assert "Очередь доставки и повторов" in response.text
        assert "Покупка SBER" in response.text
        assert "/admin/delivery/rec-1" in response.text


def test_delivery_retry_redirects(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    strategy = _make_strategy("strategy-1", author, "Momentum RU")
    recommendation = _make_published_recommendation("rec-1", strategy, author)
    session.users_by_id[admin.id] = admin
    record = SimpleNamespace(
        recommendation=recommendation,
        events=[],
        latest_delivery_event=None,
        delivery_attempts=2,
        delivered_recipients=5,
    )

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.create_bot",
        lambda _token: SimpleNamespace(session=SimpleNamespace(close=lambda: _async_return(None))),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.retry_recommendation_delivery",
        lambda _session, _recommendation_id, _bot: _async_return(record),
    )

    with _build_client(session, admin) as client:
        response = client.post("/admin/delivery/rec-1/retry", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/delivery/rec-1"


def test_strategy_list_renders(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    session.users_by_id[admin.id] = admin
    strategy = _make_strategy("strategy-1", author, "Dividend RU")

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_strategies",
        lambda _session: _async_return([strategy]),
    )

    with _build_client(session, admin) as client:
        response = client.get("/admin/strategies")

        assert response.status_code == 200
        assert "Каталог стратегий" in response.text
        assert "Dividend RU" in response.text
        assert "/admin/strategies/strategy-1/edit" in response.text


def test_strategy_create_submit_redirects_to_editor(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    session.users_by_id[admin.id] = admin

    created: dict[str, Any] = {}

    async def fake_create_strategy(_session, data):
        created["data"] = data
        strategy = _make_strategy("strategy-new", author, data.title)
        strategy.author_id = data.author_id
        strategy.slug = data.slug
        strategy.short_description = data.short_description
        strategy.full_description = data.full_description
        strategy.risk_level = data.risk_level
        strategy.status = data.status
        strategy.min_capital_rub = data.min_capital_rub
        strategy.is_public = data.is_public
        strategy.author = author
        return strategy

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_authors",
        lambda _session: _async_return([author]),
    )
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.create_strategy", fake_create_strategy)

    with _build_client(session, admin) as client:
        response = client.post(
            "/admin/strategies",
            data={
                "author_id": "author-1",
                "slug": "growth-ru",
                "title": "Growth RU",
                "short_description": "Тестовая стратегия роста",
                "full_description": "Полное описание",
                "risk_level": "high",
                "status": "draft",
                "min_capital_rub": "250000",
                "is_public": "1",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/strategies/strategy-new/edit"
        assert created["data"].slug == "growth-ru"
        assert created["data"].risk_level == RiskLevel.HIGH
        assert created["data"].status == StrategyStatus.DRAFT


def test_strategy_edit_page_renders_existing_strategy(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    strategy = _make_strategy("strategy-1", author, "Value RU")
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_authors",
        lambda _session: _async_return([author]),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.get_admin_strategy",
        lambda _session, _strategy_id: _async_return(strategy),
    )

    with _build_client(session, admin) as client:
        response = client.get("/admin/strategies/strategy-1/edit")

        assert response.status_code == 200
        assert "Редактирование стратегии" in response.text
        assert "Value RU" in response.text


def test_strategy_edit_submit_redirects_after_update(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    strategy = _make_strategy("strategy-1", author, "Value RU")
    session.users_by_id[admin.id] = admin

    updated: dict[str, Any] = {}

    async def fake_update_strategy(_session, current_strategy, data):
        updated["strategy"] = current_strategy
        updated["data"] = data
        current_strategy.title = data.title
        current_strategy.slug = data.slug
        current_strategy.short_description = data.short_description
        current_strategy.full_description = data.full_description
        current_strategy.risk_level = data.risk_level
        current_strategy.status = data.status
        current_strategy.min_capital_rub = data.min_capital_rub
        current_strategy.is_public = data.is_public
        return current_strategy

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.get_admin_strategy",
        lambda _session, _strategy_id: _async_return(strategy),
    )
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.update_strategy", fake_update_strategy)

    with _build_client(session, admin) as client:
        response = client.post(
            "/admin/strategies/strategy-1",
            data={
                "author_id": "author-1",
                "slug": "value-ru-updated",
                "title": "Value RU Updated",
                "short_description": "Обновленное описание",
                "full_description": "Обновленный текст",
                "risk_level": "low",
                "status": "published",
                "min_capital_rub": "300000",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/strategies/strategy-1/edit"
        assert updated["strategy"] is strategy
        assert updated["data"].title == "Value RU Updated"
        assert updated["data"].risk_level == RiskLevel.LOW
        assert updated["data"].status == StrategyStatus.PUBLISHED


async def _async_return(value):
    return value


async def _async_raise(exc: Exception):
    raise exc


def test_product_list_renders(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    strategy = _make_strategy("strategy-1", author, "Momentum RU")
    product = _make_product("product-1", strategy)
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_products",
        lambda _session: _async_return([product]),
    )

    with _build_client(session, admin) as client:
        response = client.get("/admin/products")

        assert response.status_code == 200
        assert "Продукты подписки" in response.text
        assert "Momentum RU Monthly" in response.text
        assert "/admin/products/product-1/edit" in response.text


def test_promo_code_list_renders(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    promo_code = _make_promo_code("promo-1", "WELCOME10")
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_promo_codes",
        lambda _session: _async_return([promo_code]),
    )

    with _build_client(session, admin) as client:
        response = client.get("/admin/promos")

        assert response.status_code == 200
        assert "Промокоды" in response.text
        assert "WELCOME10" in response.text
        assert "/admin/promos/promo-1/edit" in response.text


def test_promo_code_create_redirects_to_editor(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    session.users_by_id[admin.id] = admin

    async def fake_create(_session, data):
        promo_code = _make_promo_code("promo-new", data.code)
        promo_code.discount_percent = data.discount_percent
        promo_code.discount_amount_rub = data.discount_amount_rub
        promo_code.max_redemptions = data.max_redemptions
        return promo_code

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_promo_codes",
        lambda _session: _async_return([]),
    )
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.create_admin_promo_code", fake_create)

    with _build_client(session, admin) as client:
        response = client.post(
            "/admin/promos",
            data={
                "code": "WELCOME10",
                "description": "launch promo",
                "discount_percent": "10",
                "discount_amount_rub": "",
                "max_redemptions": "100",
                "expires_at": "",
                "is_active": "1",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/promos/promo-new/edit"


def test_lead_analytics_page_renders(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_lead_source_analytics",
        lambda _session: _async_return(
            [
                SimpleNamespace(
                    source_name="ads_meta",
                    source_type="ads",
                    users_total=3,
                    subscriptions_total=2,
                    active_subscriptions=1,
                    payments_total=2,
                    paid_payments=1,
                    revenue_rub=4410,
                )
            ]
        ),
    )

    with _build_client(session, admin) as client:
        response = client.get("/admin/analytics/leads")

        assert response.status_code == 200
        assert "Источники лидов" in response.text
        assert "ads_meta" in response.text
        assert "4410 RUB" in response.text


def test_product_create_submit_redirects_to_editor(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    strategy = _make_strategy("strategy-1", author, "Momentum RU")
    bundle = _make_bundle("bundle-1", "Premium Pack")
    session.users_by_id[admin.id] = admin

    created: dict[str, Any] = {}

    async def fake_create_product(_session, data):
        created["data"] = data
        product = _make_product("product-new", strategy)
        product.product_type = data.product_type
        product.slug = data.slug
        product.title = data.title
        product.description = data.description
        product.strategy_id = data.strategy_id
        product.author_id = data.author_id
        product.bundle_id = data.bundle_id
        product.billing_period = data.billing_period
        product.price_rub = data.price_rub
        product.trial_days = data.trial_days
        product.is_active = data.is_active
        product.autorenew_allowed = data.autorenew_allowed
        product.strategy = strategy
        return product

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_authors",
        lambda _session: _async_return([author]),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_strategies",
        lambda _session: _async_return([strategy]),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_bundles",
        lambda _session: _async_return([bundle]),
    )
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.create_product", fake_create_product)

    with _build_client(session, admin) as client:
        response = client.post(
            "/admin/products",
            data={
                "product_type": "strategy",
                "slug": "momentum-ru-month",
                "title": "Momentum RU Monthly",
                "description": "Месячная подписка",
                "strategy_id": "strategy-1",
                "billing_period": "month",
                "price_rub": "4900",
                "trial_days": "7",
                "is_active": "1",
                "autorenew_allowed": "1",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/products/product-new/edit"
        assert created["data"].product_type == ProductType.STRATEGY
        assert created["data"].billing_period == BillingPeriod.MONTH
        assert created["data"].strategy_id == "strategy-1"


def test_product_edit_submit_redirects_after_update(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    strategy = _make_strategy("strategy-1", author, "Momentum RU")
    product = _make_product("product-1", strategy)
    session.users_by_id[admin.id] = admin

    updated: dict[str, Any] = {}

    async def fake_update_product(_session, current_product, data):
        updated["product"] = current_product
        updated["data"] = data
        current_product.title = data.title
        current_product.slug = data.slug
        current_product.description = data.description
        current_product.price_rub = data.price_rub
        current_product.trial_days = data.trial_days
        return current_product

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.get_admin_product",
        lambda _session, _product_id: _async_return(product),
    )
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.update_product", fake_update_product)

    with _build_client(session, admin) as client:
        response = client.post(
            "/admin/products/product-1",
            data={
                "product_type": "strategy",
                "slug": "momentum-ru-quarter",
                "title": "Momentum RU Quarter",
                "description": "Квартальная подписка",
                "strategy_id": "strategy-1",
                "billing_period": "quarter",
                "price_rub": "12900",
                "trial_days": "14",
                "is_active": "1",
                "autorenew_allowed": "1",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/products/product-1/edit"
        assert updated["product"] is product
        assert updated["data"].billing_period == BillingPeriod.QUARTER
        assert updated["data"].price_rub == 12900


def test_author_registry_renders_active_and_inactive(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    active_author = _make_author("author-1", "author-user-1", "Alpha Desk")
    inactive_author = _make_author("author-2", "author-user-2", "Beta Desk")
    inactive_author.is_active = False
    session.users_by_id[admin.id] = admin

    async def fake_list_authors(_session, status_filter="all"):
        items = [active_author, inactive_author]
        if status_filter == "active":
            return [active_author]
        if status_filter == "inactive":
            return [inactive_author]
        return items

    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_authors", fake_list_authors)

    with _build_client(session, admin) as client:
        response = client.get("/admin/authors?status_filter=all")

        assert response.status_code == 200
        assert "Alpha Desk" in response.text
        assert "Beta Desk" in response.text
        assert "отключён" in response.text


def test_author_registry_filters_inactive(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    inactive_author = _make_author("author-2", "author-user-2", "Beta Desk")
    inactive_author.is_active = False
    session.users_by_id[admin.id] = admin

    async def fake_list_authors(_session, status_filter="all"):
        assert status_filter == "inactive"
        return [inactive_author]

    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_authors", fake_list_authors)

    with _build_client(session, admin) as client:
        response = client.get("/admin/authors?status_filter=inactive")

        assert response.status_code == 200
        assert "Beta Desk" in response.text
        assert "Alpha Desk" not in response.text


def test_author_registry_invite_link_is_absolute(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    author.user.telegram_user_id = None
    session.users_by_id[admin.id] = admin

    monkeypatch.setenv("BASE_URL", "https://pct.test.ptfin.ru")
    reset_settings_cache()
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_authors", lambda _session, status_filter="all": _async_return([author]))

    with _build_client(session, admin) as client:
        response = client.get("/admin/authors?status_filter=all")

        assert response.status_code == 200
        assert "https://pct.test.ptfin.ru/login?invite_token=" in response.text
    reset_settings_cache()


def test_staff_registry_renders_filters_and_actions(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    dual_role = _make_admin_user()
    dual_role.id = "staff-2"
    dual_role.email = "dual@example.com"
    dual_role.full_name = "Dual Role"
    dual_role.roles = [
        Role(slug=RoleSlug.ADMIN, title="Admin"),
        Role(slug=RoleSlug.AUTHOR, title="Author"),
    ]
    dual_role.author_profile = AuthorProfile(
        id="author-dual",
        user_id=dual_role.id,
        display_name="Dual Role",
        slug="dual-role",
        is_active=True,
    )
    dual_role.status = UserStatus.ACTIVE
    dual_role.telegram_user_id = None
    session.users_by_id[admin.id] = admin

    async def fake_list_staff(_session, role_filter="all"):
        assert role_filter == "multi-role"
        return [dual_role]

    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_staff", fake_list_staff)

    with _build_client(session, admin) as client:
        response = client.get("/admin/staff?role_filter=multi-role")

        assert response.status_code == 200
        assert "Команда и роли" in response.text
        assert "Dual Role" in response.text
        assert "multi-role" in response.text
        assert "Снять роль администратора" in response.text
        assert "invite_token=" in response.text


def test_staff_registry_invite_link_is_absolute(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    invited_admin = _make_admin_user()
    invited_admin.id = "staff-2"
    invited_admin.email = "ops@example.com"
    invited_admin.full_name = "Ops Admin"
    invited_admin.telegram_user_id = None
    invited_admin.status = UserStatus.INVITED
    session.users_by_id[admin.id] = admin

    monkeypatch.setenv("BASE_URL", "https://pct.test.ptfin.ru")
    reset_settings_cache()
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_staff", lambda _session, role_filter="all": _async_return([invited_admin]))

    with _build_client(session, admin) as client:
        response = client.get("/admin/staff")

        assert response.status_code == 200
        assert "https://pct.test.ptfin.ru/login?invite_token=" in response.text
    reset_settings_cache()


def test_staff_create_admin_redirects_to_registry(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    session.users_by_id[admin.id] = admin
    created: dict[str, object] = {}

    async def fake_create_admin(_session, data):
        created["data"] = data
        return _make_admin_user()

    monkeypatch.setattr("pitchcopytrade.api.routes.admin.create_admin_staff_user", fake_create_admin)

    with _build_client(session, admin) as client:
        response = client.post(
            "/admin/staff/admins",
            data={"display_name": "Ops Admin", "email": "ops@example.com", "telegram_user_id": ""},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/staff"
        assert created["data"].role_slugs == (RoleSlug.ADMIN,)


def test_staff_create_admin_renders_business_error(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.create_admin_staff_user",
        lambda _session, _data: _async_raise(ValueError("Пользователь с таким email уже существует.")),
    )
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_staff", lambda _session, role_filter="all": _async_return([]))

    with _build_client(session, admin) as client:
        response = client.post(
            "/admin/staff/admins",
            data={"display_name": "Ops Admin", "email": "ops@example.com", "telegram_user_id": ""},
        )

        assert response.status_code == 422
        assert "Пользователь с таким email уже существует." in response.text


def test_staff_grant_admin_role_redirects(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    session.users_by_id[admin.id] = admin
    captured: dict[str, object] = {}

    async def fake_grant_role(_session, *, actor_user_id, target_user_id, role_slug):
        captured["actor_user_id"] = actor_user_id
        captured["target_user_id"] = target_user_id
        captured["role_slug"] = role_slug
        return author.user

    monkeypatch.setattr("pitchcopytrade.api.routes.admin.grant_staff_role", fake_grant_role)

    with _build_client(session, admin) as client:
        response = client.post(
            f"/admin/staff/{author.user.id}/roles",
            data={"role_slug": "admin"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/staff"
        assert captured["actor_user_id"] == admin.id
        assert captured["target_user_id"] == author.user.id
        assert captured["role_slug"] == RoleSlug.ADMIN


def test_staff_edit_updates_existing_row(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    session.users_by_id[admin.id] = admin
    captured: dict[str, object] = {}

    async def fake_update_staff(_session, *, user_id, data):
        captured["user_id"] = user_id
        captured["data"] = data
        return _make_admin_user()

    monkeypatch.setattr("pitchcopytrade.api.routes.admin.update_admin_staff_user", fake_update_staff)

    with _build_client(session, admin) as client:
        response = client.post(
            "/admin/staff/staff-2/edit",
            data={
                "display_name": "Ops Admin",
                "email": "ops@example.com",
                "telegram_user_id": "12345",
                "role_slugs": ["admin", "author"],
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/staff"
        assert captured["user_id"] == "staff-2"
        assert captured["data"].display_name == "Ops Admin"
        assert captured["data"].email == "ops@example.com"
        assert captured["data"].telegram_user_id == 12345
        assert captured["data"].role_slugs == (RoleSlug.ADMIN, RoleSlug.AUTHOR)


def test_staff_activate_uses_explicit_status_action(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    session.users_by_id[admin.id] = admin
    captured: dict[str, object] = {}

    async def fake_set_status(_session, *, actor_user_id, user_id, is_active):
        captured["actor_user_id"] = actor_user_id
        captured["user_id"] = user_id
        captured["is_active"] = is_active
        return _make_admin_user()

    monkeypatch.setattr("pitchcopytrade.api.routes.admin.set_admin_staff_user_status", fake_set_status)

    with _build_client(session, admin) as client:
        response = client.post("/admin/staff/staff-2/activate", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/staff"
        assert captured == {"actor_user_id": admin.id, "user_id": "staff-2", "is_active": True}


def test_author_edit_updates_existing_row(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    session.users_by_id[admin.id] = admin
    captured: dict[str, object] = {}

    async def fake_update_author(_session, *, author_id, data):
        captured["author_id"] = author_id
        captured["data"] = data
        return _make_author("author-1", "author-user-1", "Alpha Desk")

    monkeypatch.setattr("pitchcopytrade.api.routes.admin.update_admin_author", fake_update_author)

    with _build_client(session, admin) as client:
        response = client.post(
            "/admin/authors/author-1/edit",
            data={
                "display_name": "Alpha Desk",
                "email": "alpha@example.com",
                "telegram_user_id": "777",
                "requires_moderation": "on",
                "status_value": "inactive",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/authors"
        assert captured["author_id"] == "author-1"
        assert captured["data"].display_name == "Alpha Desk"
        assert captured["data"].email == "alpha@example.com"
        assert captured["data"].telegram_user_id == 777
        assert captured["data"].requires_moderation is True
        assert captured["data"].is_active is False


async def test_file_mode_oversight_email_uses_active_admins(monkeypatch) -> None:
    created_user = User(id="created-1", email="new@example.com", full_name="New Staff", status=UserStatus.INVITED)
    admin = _make_admin_user()
    inactive_admin = _make_admin_user()
    inactive_admin.id = "admin-2"
    inactive_admin.email = "inactive@example.com"
    inactive_admin.status = UserStatus.INACTIVE
    graph = SimpleNamespace(users={created_user.id: created_user, admin.id: admin, inactive_admin.id: inactive_admin})
    delivered: list[tuple[str | None, str, str]] = []

    monkeypatch.setattr(admin_service, "_file_admin_graph", lambda: (graph, object()))

    async def fake_send_email(*, to_email: str | None, subject: str, body: str):
        delivered.append((to_email, subject, body))
        return True, None

    monkeypatch.setattr(admin_service, "_send_email_message", fake_send_email)

    await admin_service._send_admin_oversight_email(
        None,
        user=created_user,
        role_slugs=(RoleSlug.ADMIN,),
        sent=True,
        error=None,
    )

    assert delivered == [
        (
            "admin@example.com",
            "Контроль staff onboarding — PitchCopyTrade",
            "Создан администратор: New Staff\nРоли: admin\nПриглашение: отправлено",
        )
    ]


def test_staff_revoke_admin_role_renders_governance_error(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.revoke_staff_role",
        lambda _session, **_kwargs: _async_raise(ValueError("Нельзя снять у себя роль последнего активного администратора.")),
    )
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_staff", lambda _session, role_filter="all": _async_return([admin]))

    with _build_client(session, admin) as client:
        response = client.post(f"/admin/staff/{admin.id}/roles/admin/remove")

        assert response.status_code == 422
        assert "Нельзя снять у себя роль последнего активного администратора." in response.text


def test_product_create_shows_validation_error_for_missing_target(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    strategy = _make_strategy("strategy-1", author, "Momentum RU")
    bundle = _make_bundle("bundle-1", "Premium Pack")
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_authors",
        lambda _session: _async_return([author]),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_strategies",
        lambda _session: _async_return([strategy]),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_bundles",
        lambda _session: _async_return([bundle]),
    )

    with _build_client(session, admin) as client:
        response = client.post(
            "/admin/products",
            data={
                "product_type": "strategy",
                "slug": "broken-product",
                "title": "Broken Product",
                "billing_period": "month",
                "price_rub": "1000",
                "trial_days": "0",
            },
        )

        assert response.status_code == 422
        assert "нужно выбрать стратегию" in response.text


def test_payment_list_renders(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    strategy = _make_strategy("strategy-1", author, "Momentum RU")
    product = _make_product("product-1", strategy)
    payment = _make_payment("payment-1", product)
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_payments",
        lambda _session: _async_return([payment]),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.get_payment_review_stats",
        lambda _session: _async_return(
            SimpleNamespace(
                pending_payments=1,
                paid_payments=0,
                pending_subscriptions=1,
                active_subscriptions=0,
            )
        ),
    )

    with _build_client(session, admin) as client:
        response = client.get("/admin/payments")

        assert response.status_code == 200
        assert "Платежи и активации" in response.text
        assert "Lead User" in response.text
        assert "MANUAL-MOMENTUM-ABCD1234" in response.text


def test_payment_detail_renders(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    strategy = _make_strategy("strategy-1", author, "Momentum RU")
    product = _make_product("product-1", strategy)
    payment = _make_payment("payment-1", product)
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.get_admin_payment",
        lambda _session, _payment_id: _async_return(payment),
    )

    with _build_client(session, admin) as client:
        response = client.get("/admin/payments/payment-1")

        assert response.status_code == 200
        assert "Проверка платежа" in response.text
        assert "Lead User" in response.text
        assert "Momentum RU Monthly" in response.text
        assert "Ручная скидка" in response.text


def test_payment_confirm_redirects_after_activation(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    strategy = _make_strategy("strategy-1", author, "Momentum RU")
    product = _make_product("product-1", strategy)
    payment = _make_payment("payment-1", product)
    session.users_by_id[admin.id] = admin

    called: dict[str, Any] = {}

    async def fake_confirm(_session, current_payment):
        called["payment"] = current_payment
        current_payment.status = PaymentStatus.PAID
        current_payment.subscriptions[0].status = SubscriptionStatus.TRIAL
        return current_payment, current_payment.subscriptions

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.get_admin_payment",
        lambda _session, _payment_id: _async_return(payment),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.confirm_payment_and_activate_subscription",
        fake_confirm,
    )

    with _build_client(session, admin) as client:
        response = client.post("/admin/payments/payment-1/confirm", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/payments/payment-1"
        assert called["payment"] is payment
        assert payment.status == PaymentStatus.PAID


def test_payment_manual_discount_redirects(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    strategy = _make_strategy("strategy-1", author, "Momentum RU")
    product = _make_product("product-1", strategy)
    payment = _make_payment("payment-1", product)
    session.users_by_id[admin.id] = admin

    called: dict[str, Any] = {}

    async def fake_apply(_session, current_payment, *, discount_rub: int):
        called["payment"] = current_payment
        called["discount_rub"] = discount_rub
        current_payment.final_amount_rub = current_payment.amount_rub - discount_rub
        return current_payment

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.get_admin_payment",
        lambda _session, _payment_id: _async_return(payment),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.apply_manual_discount_to_payment",
        fake_apply,
    )

    with _build_client(session, admin) as client:
        response = client.post(
            "/admin/payments/payment-1/manual-discount",
            data={"discount_rub": "99"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/payments/payment-1"
        assert called["payment"] is payment
        assert called["discount_rub"] == 99
