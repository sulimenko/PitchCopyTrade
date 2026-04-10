from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient
import pytest

from pitchcopytrade.api.main import create_app
from pitchcopytrade.api.deps.auth import require_admin
from pitchcopytrade.services import admin as admin_service
from pitchcopytrade.core.config import reset_settings_cache
from pitchcopytrade.db.session import get_optional_db_session
from pitchcopytrade.auth.passwords import hash_password
from pitchcopytrade.db.models.accounts import AuthorProfile, Role, User
from pitchcopytrade.db.models.catalog import Bundle, Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import Payment, PromoCode, Subscription, UserConsent
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.commerce import LegalDocument
from pitchcopytrade.db.models.enums import (
    InviteDeliveryStatus,
    LegalDocumentType,
    PaymentProvider,
    PaymentStatus,
    ProductType,
    MessageKind,
    MessageStatus,
    RiskLevel,
    RoleSlug,
    StrategyStatus,
    SubscriptionStatus,
    UserStatus,
)
from pitchcopytrade.repositories.file_graph import FileDatasetGraph


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


class FakeGovernanceDbSession:
    def __init__(self, *, profile: AuthorProfile, active_admins: int) -> None:
        self.profile = profile
        self.active_admins = active_admins

    async def execute(self, query: Any):
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))

        class Result:
            def __init__(self, value: Any) -> None:
                self._value = value

            def scalar_one_or_none(self) -> Any:
                return self._value

            def scalar_one(self) -> Any:
                return self._value

        if "FROM author_profiles" in compiled and "WHERE author_profiles.id" in compiled:
            return Result(self.profile)
        if "count(distinct(users.id))" in compiled:
            return Result(self.active_admins)

        raise AssertionError(f"Unexpected query in FakeGovernanceDbSession: {compiled}")


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
        duration_days=30,
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


def _make_published_message(message_id: str, strategy: Strategy, author: AuthorProfile) -> Message:
    message = Message(
        id=message_id,
        strategy_id=strategy.id,
        author_id=author.id,
        kind=MessageKind.IDEA,
        status=MessageStatus.PUBLISHED,
        title="Покупка SBER",
        text={
            "format": "html",
            "title": "Покупка SBER",
            "body": "<p>Сильный спрос</p>",
            "plain": "Сильный спрос",
        },
        documents=[],
        deals=[
            {
                "instrument": "instrument-1",
                "ticker": "SBER",
                "side": "buy",
                "price": "101.5",
                "quantity": "10",
                "amount": "1015",
            }
        ],
        published=datetime(2026, 3, 11, tzinfo=timezone.utc),
    )
    message.strategy = strategy
    message.author = author
    return message


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
    messages: list[str] = []
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.logger.info",
        lambda message, *args, **kwargs: messages.append(message % args),
    )

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.get_admin_dashboard_stats",
        lambda _session: _async_return(
            SimpleNamespace(
                authors_total=3,
                strategies_total=7,
                strategies_public=5,
                active_subscriptions=14,
                messages_live=9,
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
        assert any("admin_dashboard trace" in message for message in messages)


def test_admin_dashboard_renders_failure_fallback(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    session.users_by_id[admin.id] = admin
    messages: list[str] = []
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.logger.info",
        lambda message, *args, **kwargs: messages.append(message % args),
    )

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.get_admin_dashboard_stats",
        lambda _session: _async_raise(RuntimeError("boom")),
    )

    with _build_client(session, admin) as client:
        response = client.get("/admin/dashboard")

        assert response.status_code == 200
        assert "Не удалось загрузить панель администратора" in response.text
        assert any("admin_dashboard_fail trace" in message for message in messages)
        assert any("dashboard_failure" in message for message in messages)


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
                messages_live=0,
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
        assert "/static/vendor/tabulator/tabulator.min.js" in response.text
        assert "/static/staff/tabulator-bootstrap.js" in response.text


def test_local_tabulator_vendor_asset_is_served() -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    session.users_by_id[admin.id] = admin

    with _build_client(session, admin) as client:
        response = client.get("/static/vendor/tabulator/tabulator.min.js")

        assert response.status_code == 200
        assert "Tabulator" in response.text


def test_staff_tabulator_bootstrap_uses_fixed_layout_on_desktop() -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    session.users_by_id[admin.id] = admin

    with _build_client(session, admin) as client:
        response = client.get("/static/staff/tabulator-bootstrap.js")

        assert response.status_code == 200
        assert 'PCTTabulator' in response.text
        assert 'new Tabulator' in response.text


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
        assert "Найти подписки" in response.text
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
        assert "Клиент и доступ" in response.text
        assert "Что получает клиент" in response.text
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
        assert "Новая версия сначала создаётся как черновик" in response.text
        assert "Публичная оферта" in response.text
        assert "/admin/legal/doc-offer/edit" in response.text


def test_legal_document_edit_page_renders_compact_sections(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    document = _make_legal_document("doc-offer", LegalDocumentType.OFFER)
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_legal_documents", lambda _session: _async_return([document]))
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.get_admin_legal_document", lambda _session, _document_id: _async_return(document))

    with _build_client(session, admin) as client:
        response = client.get("/admin/legal/doc-offer/edit")

        assert response.status_code == 200
        assert "Основное" in response.text
        assert "Контент" in response.text
        assert "Контекст версии" in response.text
        assert "Доступные версии" in response.text


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
    message = _make_published_message("rec-1", strategy, author)
    session.users_by_id[admin.id] = admin
    record = SimpleNamespace(
        message=message,
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
        assert "Alpha Desk" in response.text
        assert "/admin/delivery/rec-1" in response.text


def test_delivery_detail_renders_compact_sections(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    strategy = _make_strategy("strategy-1", author, "Momentum RU")
    message = _make_published_message("rec-1", strategy, author)
    session.users_by_id[admin.id] = admin
    record = SimpleNamespace(
        message=message,
        events=[],
        latest_delivery_event=None,
        delivery_attempts=1,
        delivered_recipients=3,
    )

    monkeypatch.setattr("pitchcopytrade.api.routes.admin.get_admin_delivery_record", lambda _session, _recommendation_id: _async_return(record))

    with _build_client(session, admin) as client:
        response = client.get("/admin/delivery/rec-1")

        assert response.status_code == 200
        assert "Сводка по доставке" in response.text
        assert "Повторить доставку в Telegram" in response.text
        assert "События доставки" in response.text


def test_delivery_retry_redirects(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    strategy = _make_strategy("strategy-1", author, "Momentum RU")
    message = _make_published_message("rec-1", strategy, author)
    session.users_by_id[admin.id] = admin
    record = SimpleNamespace(
        message=message,
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
        "pitchcopytrade.api.routes.admin.retry_message_delivery",
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


def test_strategy_create_submit_rerenders_form_for_empty_slug(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_authors",
        lambda _session: _async_return([author]),
    )

    with _build_client(session, admin) as client:
        response = client.post(
            "/admin/strategies",
            data={
                "author_id": "author-1",
                "slug": "",
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

        assert response.status_code == 422
        assert "Укажите код стратегии" in response.text
        assert "Код стратегии (латиницей)" in response.text


def test_strategy_create_submit_renders_multiple_field_errors(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    session.users_by_id[admin.id] = admin
    author = _make_author("author-1", "author-user-1", "Alpha Desk")

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_authors",
        lambda _session: _async_return([author]),
    )

    with _build_client(session, admin) as client:
        response = client.post(
            "/admin/strategies",
            data={
                "author_id": "",
                "slug": "",
                "title": "",
                "short_description": "",
                "full_description": "",
                "risk_level": "",
                "status": "",
                "min_capital_rub": "abc",
                "is_public": "1",
            },
            follow_redirects=False,
        )

        assert response.status_code == 422
        assert "Требования к заполнению" in response.text
        assert "has-error" in response.text
        assert "Выберите автора стратегии" in response.text
        assert "Укажите код стратегии" in response.text
        assert "Название стратегии обязательно" in response.text
        assert "Короткое описание обязательно" in response.text
        assert "Минимальный капитал должен быть целым числом" in response.text


def test_strategy_create_submit_shows_duplicate_slug_error(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_authors",
        lambda _session: _async_return([author]),
    )

    async def fake_create_strategy(_session, _data):
        raise ValueError("Код стратегии «growth-ru» уже используется. Выберите другой.")

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

        assert response.status_code == 422
        assert "уже используется" in response.text
        assert "Growth RU" in response.text


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
        assert "В реестре сразу видны коммерческие условия" in response.text
        assert "Momentum RU Monthly" in response.text
        assert "/admin/products/product-1/edit" in response.text


def test_product_edit_page_renders_compact_sections(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    strategy = _make_strategy("strategy-1", author, "Momentum RU")
    product = _make_product("product-1", strategy)
    bundle = _make_bundle("bundle-1", "Premium Pack")
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_authors", lambda _session: _async_return([author]))
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_strategies", lambda _session: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_bundles", lambda _session: _async_return([bundle]))
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.get_admin_product", lambda _session, _product_id: _async_return(product))

    with _build_client(session, admin) as client:
        response = client.get("/admin/products/product-1/edit")

        assert response.status_code == 200
        assert "Основное" in response.text
        assert "Цель доступа" in response.text
        assert "Коммерция и доступность" in response.text
        assert "Подсказки по тарифу" in response.text


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
        assert "Сразу видны код, скидка, лимиты" in response.text
        assert "WELCOME10" in response.text
        assert "/admin/promos/promo-1/edit" in response.text


def test_promo_code_edit_page_renders_compact_sections(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    promo_code = _make_promo_code("promo-1", "WELCOME10")
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_promo_codes", lambda _session: _async_return([promo_code]))
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.get_admin_promo_code", lambda _session, _promo_code_id: _async_return(promo_code))

    with _build_client(session, admin) as client:
        response = client.get("/admin/promos/promo-1/edit")

        assert response.status_code == 200
        assert "Основное" in response.text
        assert "Скидка и срок действия" in response.text
        assert "Текущая карточка" in response.text


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


def test_promo_code_create_shows_single_summary_error_for_missing_discount(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_promo_codes",
        lambda _session: _async_return([]),
    )

    with _build_client(session, admin) as client:
        response = client.post(
            "/admin/promos",
            data={
                "code": "WELCOME10",
                "description": "launch promo",
                "discount_percent": "",
                "discount_amount_rub": "",
                "max_redemptions": "100",
                "expires_at": "",
                "is_active": "1",
            },
            follow_redirects=False,
        )

        assert response.status_code == 422
        assert "Укажите скидку в процентах ИЛИ фиксированную сумму в рублях" in response.text
        assert "Нужно указать discount percent" not in response.text
        assert "Используйте либо discount percent" not in response.text


def test_promo_code_create_shows_duplicate_code_error(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_promo_codes",
        lambda _session: _async_return([_make_promo_code("promo-1", "WELCOME10")]),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.create_admin_promo_code",
        lambda _session, _data: _async_raise(ValueError("Промокод «WELCOME10» уже существует. Выберите другой код.")),
    )

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

        assert response.status_code == 422
        assert "уже существует" in response.text
        assert "Код промокода" in response.text


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
        assert "рабочую таблицу атрибуции" in response.text
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
        product.duration_days = data.duration_days
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
                "duration_days": "60",
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
        assert created["data"].duration_days == 60
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
        current_product.duration_days = data.duration_days
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
                "duration_days": "90",
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
        assert updated["data"].duration_days == 90
        assert updated["data"].price_rub == 12900


def test_product_form_renders_duration_targets_and_slug_autofill(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    strategy = _make_strategy("strategy-1", author, "Momentum RU")
    bundle = _make_bundle("bundle-1", "Premium Pack")
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_authors", lambda _session: _async_return([author]))
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_strategies", lambda _session: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_bundles", lambda _session: _async_return([bundle]))

    with _build_client(session, admin) as client:
        response = client.get("/admin/products/new")

        assert response.status_code == 200
        assert 'name="duration_days"' in response.text
        assert 'data-target="strategy"' in response.text
        assert 'data-target="author"' in response.text
        assert 'data-target="bundle"' in response.text
        assert 'data-slug="momentum-ru"' in response.text
        assert 'data-author="Alpha Desk"' in response.text
        assert 'readonly' in response.text
        assert "Введите 0 для бесплатного продукта." in response.text


def test_product_create_rejects_invalid_duration_days(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", "author-user-1", "Alpha Desk")
    strategy = _make_strategy("strategy-1", author, "Momentum RU")
    bundle = _make_bundle("bundle-1", "Premium Pack")
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_authors", lambda _session: _async_return([author]))
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_strategies", lambda _session: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_bundles", lambda _session: _async_return([bundle]))

    with _build_client(session, admin) as client:
        response = client.post(
            "/admin/products",
            data={
                "product_type": "strategy",
                "slug": "broken-product",
                "title": "Broken Product",
                "strategy_id": "strategy-1",
                "duration_days": "45",
                "price_rub": "1000",
                "trial_days": "0",
            },
        )

        assert response.status_code == 422
        assert "Выберите корректный период подписки" in response.text


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
        assert 'class="staff-rail-link is-active" href="/admin/authors"' not in response.text


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


def test_author_registry_handles_sparse_related_data(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    sparse_author = AuthorProfile(
        id="author-broken",
        user_id="missing-user",
        display_name="Broken Desk",
        slug="broken-desk",
        is_active=True,
        requires_moderation=True,
    )
    sparse_author.user = None
    partial_invite_author = _make_author("author-2", "author-user-2", "Invite Desk")
    partial_invite_author.user.email = None
    partial_invite_author.user.telegram_user_id = None
    partial_invite_author.user.roles = []
    partial_invite_author.user.invite_delivery_status = None
    partial_invite_author.user.invite_delivery_error = "SMTP timeout"
    partial_invite_author.user.invite_delivery_updated_at = datetime(2026, 3, 20, tzinfo=timezone.utc)
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_authors",
        lambda _session, status_filter="all": _async_return([sparse_author, partial_invite_author]),
    )

    with _build_client(session, admin) as client:
        response = client.get("/admin/authors")

        assert response.status_code == 200
        assert "Broken Desk" in response.text
        assert "Связанный staff-аккаунт не найден." in response.text
        assert "нет staff bind" in response.text
        assert "Недоступно без связанного staff-аккаунта." in response.text
        assert "Invite Desk" in response.text
        assert "invite-данные неполные" in response.text
        assert "SMTP timeout" in response.text
        assert "/admin/staff//invite/resend" not in response.text


def test_author_registry_renders_controlled_state_on_internal_failure(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    session.users_by_id[admin.id] = admin

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.admin.list_admin_authors",
        lambda _session, status_filter="all": _async_raise(RuntimeError("boom")),
    )

    with _build_client(session, admin) as client:
        response = client.get("/admin/authors")

        assert response.status_code == 200
        assert "Не удалось загрузить реестр авторов. Проверьте связанные staff/user данные и повторите попытку." in response.text
        assert "Нет авторов." in response.text


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
        assert "Редактировать" in response.text
        assert "invite_token=" in response.text
        assert "staff-row-menu-panel" not in response.text
        assert 'class="staff-content"' in response.text
        assert "height: 100vh;" in response.text
        assert "flex-direction: column;" in response.text
        assert 'class="staff-rail-link " href="/admin/authors"' not in response.text


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
        assert '>https://pct.test.ptfin.ru/login?invite_token=' not in response.text
        assert "Скопировать ссылку" in response.text
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


@pytest.mark.asyncio
async def test_create_admin_staff_user_merges_existing_subscriber_metadata_in_file_mode(monkeypatch) -> None:
    existing_user = _make_admin_user()
    existing_user.id = "user-1"
    existing_user.email = "lead@example.com"
    existing_user.full_name = "Lead User"
    existing_user.timezone = "Europe/Moscow"
    existing_user.telegram_user_id = 777001
    existing_user.invite_token_version = 2
    existing_user.invite_delivery_status = InviteDeliveryStatus.FAILED
    existing_user.invite_delivery_error = "stale invite"
    existing_user.invite_delivery_updated_at = datetime(2026, 3, 20, tzinfo=timezone.utc)
    existing_user.roles = []

    graph = FileDatasetGraph(
        roles={},
        users={existing_user.id: existing_user},
        authors={},
        lead_sources={},
        instruments={},
        strategies={},
        bundles={},
        bundle_members=[],
        products={},
        promo_codes={},
        legal_documents={},
        payments={},
        subscriptions={},
        user_consents={},
        audit_events={},
        notification_logs={},
        messages={},
    )

    class DummyStore:
        def save_many(self, _datasets):
            return None

    monkeypatch.setattr("pitchcopytrade.services.admin._file_admin_graph", lambda: (graph, DummyStore()))

    result = await admin_service.create_admin_staff_user(
        None,
        admin_service.StaffCreateData(
            display_name="Ops Admin",
            email="ops@example.com",
            telegram_user_id=777001,
            role_slugs=(RoleSlug.ADMIN,),
        ),
        skip_invite=True,
    )

    assert result.id == existing_user.id
    assert result.email == "ops@example.com"
    assert result.full_name == "Ops Admin"
    assert result.timezone == "Europe/Moscow"
    assert result.telegram_user_id == 777001
    assert result.invite_token_version == 1
    assert result.invite_delivery_status is None
    assert result.invite_delivery_error is None
    assert result.invite_delivery_updated_at is None
    assert RoleSlug.ADMIN in {role.slug for role in result.roles}


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

    async def fake_update_staff(_session, *, actor_user_id, user_id, data):
        captured["actor_user_id"] = actor_user_id
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
        assert captured["actor_user_id"] == admin.id


def test_staff_edit_renders_governance_error_for_last_active_admin(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    session.users_by_id[admin.id] = admin

    async def fake_update_staff(_session, *, actor_user_id, user_id, data):
        assert actor_user_id == admin.id
        assert user_id == admin.id
        assert data.role_slugs == (RoleSlug.AUTHOR,)
        raise ValueError("Нельзя снять у себя роль последнего активного администратора.")

    monkeypatch.setattr("pitchcopytrade.api.routes.admin.update_admin_staff_user", fake_update_staff)
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_staff", lambda _session, role_filter="all": _async_return([admin]))

    with _build_client(session, admin) as client:
        response = client.post(
            f"/admin/staff/{admin.id}/edit",
            data={
                "display_name": "Admin User",
                "email": "admin@example.com",
                "telegram_user_id": "",
                "role_slugs": ["author"],
            },
            follow_redirects=False,
        )

        assert response.status_code == 422
        assert "Нельзя снять у себя роль последнего активного администратора." in response.text


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

    async def fake_update_author(_session, *, actor_user_id, author_id, data):
        captured["actor_user_id"] = actor_user_id
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
        assert captured["actor_user_id"] == admin.id


@pytest.mark.parametrize(
    ("mode", "actor_user_id", "expected_message"),
    [
        ("file", "admin-1", "Нельзя снять у себя роль последнего активного администратора."),
        ("file", "admin-2", "Нельзя снять роль у последнего активного администратора."),
        ("db", "admin-1", "Нельзя снять у себя роль последнего активного администратора."),
        ("db", "admin-2", "Нельзя снять роль у последнего активного администратора."),
    ],
)
async def test_update_admin_author_blocks_last_active_admin_role_removal_across_modes(
    monkeypatch,
    mode: str,
    actor_user_id: str,
    expected_message: str,
) -> None:
    profile = _make_author("author-1", "admin-1", "Admin Author")
    profile.user.status = UserStatus.ACTIVE
    profile.user.roles = [Role(slug=RoleSlug.ADMIN, title="Admin"), Role(slug=RoleSlug.AUTHOR, title="Author")]
    profile.user.author_profile = profile

    session = None
    if mode == "file":
        graph = SimpleNamespace(authors={profile.id: profile}, users={profile.user.id: profile.user}, roles={})
        monkeypatch.setattr(admin_service, "_file_admin_graph", lambda: (graph, object()))
    else:
        session = FakeGovernanceDbSession(profile=profile, active_admins=1)

    with pytest.raises(ValueError) as exc_info:
        await admin_service.update_admin_author(
            session,
            actor_user_id=actor_user_id,
            author_id=profile.id,
            data=admin_service.AdminAuthorUpdateData(
                display_name="Admin Author",
                email="admin@example.com",
                telegram_user_id=None,
                role_slugs=(RoleSlug.AUTHOR,),
                requires_moderation=False,
                is_active=True,
            ),
        )

    assert str(exc_info.value) == expected_message


@pytest.mark.asyncio
async def test_list_admin_authors_preloads_user_roles_in_db_mode() -> None:
    captured: dict[str, Any] = {}

    class CaptureSession:
        async def execute(self, query: Any):
            captured["query"] = query

            class Result:
                class Scalars:
                    def all(self) -> list[AuthorProfile]:
                        return []

                def scalars(self) -> "Result.Scalars":
                    return self.Scalars()

            return Result()

    authors = await admin_service.list_admin_authors(CaptureSession(), status_filter="all")

    assert authors == []
    option_paths = [str(getattr(option, "path", "")) for option in captured["query"]._with_options]
    assert any("AuthorProfile.user" in path and "User.roles" in path for path in option_paths)


def test_author_edit_renders_governance_error_for_last_active_admin(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    author = _make_author("author-1", admin.id, "Admin Author")
    author.user = admin
    admin.author_profile = author
    session.users_by_id[admin.id] = admin

    async def fake_update_author(_session, *, actor_user_id, author_id, data):
        assert actor_user_id == admin.id
        assert author_id == author.id
        assert data.role_slugs == (RoleSlug.AUTHOR,)
        raise ValueError("Нельзя снять у себя роль последнего активного администратора.")

    monkeypatch.setattr("pitchcopytrade.api.routes.admin.update_admin_author", fake_update_author)
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_authors", lambda _session, status_filter="all": _async_return([author]))

    with _build_client(session, admin) as client:
        response = client.post(
            f"/admin/authors/{author.id}/edit",
            data={
                "display_name": "Admin Author",
                "email": "admin@example.com",
                "telegram_user_id": "",
                "role_slugs": ["author"],
                "status_value": "active",
            },
            follow_redirects=False,
        )

        assert response.status_code == 422
        assert "Нельзя снять у себя роль последнего активного администратора." in response.text


def test_author_edit_renders_governance_error_for_other_last_active_admin(monkeypatch) -> None:
    session = FakeAsyncSession()
    admin = _make_admin_user()
    other_admin = _make_admin_user()
    other_admin.id = "admin-2"
    other_admin.email = "other-admin@example.com"
    author = _make_author("author-1", other_admin.id, "Other Admin Author")
    author.user = other_admin
    other_admin.author_profile = author
    session.users_by_id[admin.id] = admin
    session.users_by_id[other_admin.id] = other_admin

    async def fake_update_author(_session, *, actor_user_id, author_id, data):
        assert actor_user_id == admin.id
        assert author_id == author.id
        assert data.role_slugs == (RoleSlug.AUTHOR,)
        raise ValueError("Нельзя снять роль у последнего активного администратора.")

    monkeypatch.setattr("pitchcopytrade.api.routes.admin.update_admin_author", fake_update_author)
    monkeypatch.setattr("pitchcopytrade.api.routes.admin.list_admin_authors", lambda _session, status_filter="all": _async_return([author]))

    with _build_client(session, admin) as client:
        response = client.post(
            f"/admin/authors/{author.id}/edit",
            data={
                "display_name": "Other Admin Author",
                "email": "other-admin@example.com",
                "telegram_user_id": "",
                "role_slugs": ["author"],
                "status_value": "active",
            },
            follow_redirects=False,
        )

        assert response.status_code == 422
        assert "Нельзя снять роль у последнего активного администратора." in response.text


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
                "duration_days": "30",
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
        assert "Подтверждение меняет статус на paid" in response.text
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
        assert "Платёж и клиент" in response.text
        assert "Зафиксированные согласия" in response.text
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
