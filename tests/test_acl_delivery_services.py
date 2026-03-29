from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pitchcopytrade.db.models.catalog import SubscriptionProduct
from pitchcopytrade.db.models.commerce import LegalDocument
from pitchcopytrade.db.models.enums import (
    BillingPeriod,
    LegalDocumentType,
    PaymentProvider,
    PaymentStatus,
    ProductType,
    SubscriptionStatus,
)
from pitchcopytrade.services.public import (
    CheckoutRequest,
    TelegramSubscriberProfile,
    create_stub_checkout,
    create_telegram_stub_checkout,
)


class FakeSession:
    def __init__(self, documents: list[LegalDocument]) -> None:
        self.documents = documents
        self.user = None
        self.added = []

    async def list_active_checkout_documents(self):
        return self.documents

    async def find_user_by_email(self, email: str):
        if self.user is not None and self.user.email == email:
            return self.user
        return None

    async def get_user_by_telegram_id(self, telegram_user_id: int):
        if self.user is not None and self.user.telegram_user_id == telegram_user_id:
            return self.user
        return None

    def add(self, entity):
        self.added.append(entity)
        if entity.__class__.__name__ == "User":
            self.user = entity

    async def commit(self):
        return None

    async def refresh(self, entity):
        return None


def _make_documents() -> list[LegalDocument]:
    return [
        LegalDocument(
            id=f"doc-{item.value}",
            document_type=item,
            version="v1",
            title=f"{item.value} v1",
            content_md="text",
            is_active=True,
        )
        for item in (
            LegalDocumentType.DISCLAIMER,
            LegalDocumentType.OFFER,
            LegalDocumentType.PRIVACY_POLICY,
            LegalDocumentType.PAYMENT_CONSENT,
        )
    ]


def _make_product() -> SubscriptionProduct:
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
    product.payments = []
    product.subscriptions = []
    return product


@pytest.mark.asyncio
async def test_create_stub_checkout_auto_confirms_stub_manual_entities() -> None:
    session = FakeSession(_make_documents())
    product = _make_product()

    result = await create_stub_checkout(
        session,
        product=product,
        request=CheckoutRequest(
            full_name="Lead User",
            email="lead@example.com",
            timezone_name="Europe/Moscow",
            accepted_document_ids=[item.id for item in session.documents],
            lead_source_name="ads",
        ),
        now=datetime(2026, 3, 11, tzinfo=timezone.utc),
    )

    assert result.user.email == "lead@example.com"
    assert result.user.password_hash is None
    assert result.payment is not None
    assert result.payment.status == PaymentStatus.PAID
    assert result.payment.confirmed_at is not None
    assert result.subscription.status == SubscriptionStatus.ACTIVE
    assert result.subscription.is_trial is True


@pytest.mark.asyncio
async def test_create_telegram_stub_checkout_uses_telegram_identity_minimum() -> None:
    session = FakeSession(_make_documents())
    product = _make_product()

    result = await create_telegram_stub_checkout(
        session,
        product=product,
        profile=TelegramSubscriberProfile(
            telegram_user_id=12345,
            username="leaduser",
            first_name="Lead",
            last_name="User",
            timezone_name="Europe/Moscow",
            lead_source_name="telegram_bot",
        ),
        accepted_document_ids=[document.id for document in _make_documents()],
        now=datetime(2026, 3, 11, tzinfo=timezone.utc),
    )

    assert result.user.telegram_user_id == 12345
    assert result.user.username == "leaduser"
    assert result.user.email is None
    assert result.payment is not None
    assert result.payment.status == PaymentStatus.PAID
    assert result.subscription.status == SubscriptionStatus.ACTIVE


@pytest.mark.asyncio
async def test_create_stub_checkout_skips_payment_for_free_product() -> None:
    session = FakeSession(_make_documents())
    product = _make_product()
    product.price_rub = 0

    result = await create_stub_checkout(
        session,
        product=product,
        request=CheckoutRequest(
            full_name="Lead User",
            email="lead@example.com",
            timezone_name="Europe/Moscow",
            accepted_document_ids=[item.id for item in session.documents],
            lead_source_name="ads",
        ),
        now=datetime(2026, 3, 11, tzinfo=timezone.utc),
    )

    assert result.payment is None
    assert result.subscription.status == SubscriptionStatus.ACTIVE


@pytest.mark.asyncio
async def test_create_stub_checkout_uses_tbank_provider_when_enabled(monkeypatch) -> None:
    session = FakeSession(_make_documents())
    product = _make_product()

    class DummyClient:
        def __init__(self, *, terminal_key: str, password: str) -> None:
            self.terminal_key = terminal_key
            self.password = password

        async def create_sbp_checkout(self, **kwargs):
            return type(
                "Result",
                (),
                {
                    "payment_id": "777",
                    "order_id": kwargs["order_id"],
                    "payment_url": "https://pay.tbank.ru/qr/777",
                    "init_payload": {"PaymentId": "777", "Success": True},
                    "qr_payload": {"Success": True, "Data": "https://pay.tbank.ru/qr/777"},
                },
            )()

    monkeypatch.setattr(
        "pitchcopytrade.services.public.get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "payments": type(
                    "Payments",
                    (),
                    {
                        "provider": "tbank",
                        "tinkoff_terminal_key": type("Secret", (), {"get_secret_value": lambda self: "term"})(),
                        "tinkoff_secret_key": type("Secret", (), {"get_secret_value": lambda self: "secret"})(),
                    },
                )(),
                "app": type("App", (), {"base_url": "https://pct.test.ptfin.ru"})(),
            },
        )(),
    )
    monkeypatch.setattr("pitchcopytrade.services.public.TBankAcquiringClient", DummyClient)

    result = await create_stub_checkout(
        session,
        product=product,
        request=CheckoutRequest(
            full_name="Lead User",
            email="lead@example.com",
            timezone_name="Europe/Moscow",
            accepted_document_ids=[item.id for item in session.documents],
            lead_source_name="ads",
        ),
        now=datetime(2026, 3, 11, tzinfo=timezone.utc),
    )

    assert result.payment is not None
    assert result.payment.provider == PaymentProvider.TBANK
    assert result.payment_url == "https://pay.tbank.ru/qr/777"
    assert result.payment.provider_payload["provider_payment_id"] == "777"
