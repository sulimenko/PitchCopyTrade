from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.enums import (
    LegalDocumentType,
    RecommendationKind,
    RecommendationStatus,
    SubscriptionStatus,
    TradeSide,
)
from pitchcopytrade.repositories.access import FileAccessRepository
from pitchcopytrade.repositories.author import FileAuthorRepository
from pitchcopytrade.repositories.file_store import FileDataStore
from pitchcopytrade.repositories.public import FilePublicRepository
from pitchcopytrade.services.public import CheckoutRequest, create_stub_checkout
from pitchcopytrade.services.author import IncomingAttachment, RecommendationFormData, StructuredLegFormData, create_author_recommendation
from pitchcopytrade.storage.local import LocalFilesystemStorage


def _seed_demo_json(store: FileDataStore) -> None:
    now = datetime(2026, 3, 11, tzinfo=timezone.utc).isoformat()
    store.save_many(
        {
            "roles": [
                {"id": "role-admin", "slug": "admin", "title": "Admin", "created_at": now, "updated_at": now},
                {"id": "role-author", "slug": "author", "title": "Author", "created_at": now, "updated_at": now},
            ],
            "users": [
                {
                    "id": "user-author",
                    "email": "author@example.com",
                    "telegram_user_id": 111,
                    "username": "author1",
                    "full_name": "Author One",
                    "password_hash": "hash",
                    "status": "active",
                    "timezone": "Europe/Moscow",
                    "lead_source_id": None,
                    "role_ids": ["role-author"],
                    "created_at": now,
                    "updated_at": now,
                },
                {
                    "id": "user-sub",
                    "email": "sub@example.com",
                    "telegram_user_id": 222,
                    "username": "sub1",
                    "full_name": "Subscriber One",
                    "password_hash": None,
                    "status": "active",
                    "timezone": "Europe/Moscow",
                    "lead_source_id": None,
                    "role_ids": [],
                    "created_at": now,
                    "updated_at": now,
                },
            ],
            "authors": [
                {
                    "id": "author-1",
                    "user_id": "user-author",
                    "display_name": "Author One",
                    "slug": "author-one",
                    "bio": None,
                    "requires_moderation": False,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
            "author_watchlist_instruments": [
                {
                    "author_id": "author-1",
                    "instrument_id": "instrument-1",
                }
            ],
            "lead_sources": [],
            "instruments": [
                {
                    "id": "instrument-1",
                    "ticker": "SBER",
                    "name": "Sberbank",
                    "board": "TQBR",
                    "lot_size": 10,
                    "currency": "RUB",
                    "instrument_type": "equity",
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
            "strategies": [
                {
                    "id": "strategy-1",
                    "author_id": "author-1",
                    "slug": "momentum-ru",
                    "title": "Momentum RU",
                    "short_description": "desc",
                    "full_description": "full",
                    "risk_level": "medium",
                    "status": "published",
                    "min_capital_rub": 150000,
                    "is_public": True,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
            "bundles": [],
            "bundle_members": [],
            "products": [
                {
                    "id": "product-1",
                    "product_type": "strategy",
                    "slug": "momentum-ru-month",
                    "title": "Momentum RU",
                    "description": None,
                    "strategy_id": "strategy-1",
                    "author_id": None,
                    "bundle_id": None,
                    "billing_period": "month",
                    "price_rub": 499,
                    "trial_days": 7,
                    "is_active": True,
                    "autorenew_allowed": True,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
            "promo_codes": [],
            "legal_documents": [
                {
                    "id": f"doc-{doc_type.value}",
                    "document_type": doc_type.value,
                    "version": "v1",
                    "title": {
                        LegalDocumentType.DISCLAIMER: "Предупреждение о рисках",
                        LegalDocumentType.OFFER: "Публичная оферта",
                        LegalDocumentType.PRIVACY_POLICY: "Политика конфиденциальности",
                        LegalDocumentType.PAYMENT_CONSENT: "Согласие на оплату",
                    }[doc_type],
                    "content_md": "text",
                    "source_path": f"legal/{doc_type.value}/v1.md",
                    "is_active": True,
                    "published_at": now,
                    "created_at": now,
                    "updated_at": now,
                }
                for doc_type in (
                    LegalDocumentType.DISCLAIMER,
                    LegalDocumentType.OFFER,
                    LegalDocumentType.PRIVACY_POLICY,
                    LegalDocumentType.PAYMENT_CONSENT,
                )
            ],
            "payments": [
                {
                    "id": "payment-1",
                    "user_id": "user-sub",
                    "product_id": "product-1",
                    "promo_code_id": None,
                    "provider": "stub_manual",
                    "status": "paid",
                    "amount_rub": 499,
                    "discount_rub": 0,
                    "final_amount_rub": 499,
                    "currency": "RUB",
                    "external_id": None,
                    "stub_reference": "MANUAL-1",
                    "provider_payload": None,
                    "expires_at": (datetime(2026, 3, 12, tzinfo=timezone.utc)).isoformat(),
                    "confirmed_at": now,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
            "subscriptions": [
                {
                    "id": "sub-1",
                    "user_id": "user-sub",
                    "product_id": "product-1",
                    "payment_id": "payment-1",
                    "lead_source_id": None,
                    "applied_promo_code_id": None,
                    "status": "active",
                    "autorenew_enabled": True,
                    "is_trial": False,
                    "manual_discount_rub": 0,
                    "start_at": now,
                    "end_at": (datetime(2026, 4, 10, tzinfo=timezone.utc)).isoformat(),
                    "created_at": now,
                    "updated_at": now,
                }
            ],
            "user_consents": [],
            "recommendations": [
                {
                    "id": "rec-1",
                    "strategy_id": "strategy-1",
                    "author_id": "author-1",
                    "moderated_by_user_id": None,
                    "kind": "new_idea",
                    "status": "published",
                    "title": "Покупка SBER",
                    "summary": "Сильный спрос",
                    "thesis": "Тезис",
                    "market_context": "Контекст",
                    "requires_moderation": False,
                    "scheduled_for": None,
                    "published_at": now,
                    "closed_at": None,
                    "cancelled_at": None,
                    "moderation_comment": None,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
            "recommendation_legs": [
                {
                    "id": "leg-1",
                    "recommendation_id": "rec-1",
                    "instrument_id": "instrument-1",
                    "side": "buy",
                    "entry_from": "101.5",
                    "entry_to": "102.0",
                    "stop_loss": "99.9",
                    "take_profit_1": "106.2",
                    "take_profit_2": None,
                    "take_profit_3": None,
                    "time_horizon": "1-3 дня",
                    "note": "Основной сценарий",
                    "created_at": now,
                    "updated_at": now,
                }
            ],
            "recommendation_attachments": [
                {
                    "id": "att-1",
                    "recommendation_id": "rec-1",
                    "uploaded_by_user_id": "user-author",
                    "object_key": "recommendations/rec-1/file.pdf",
                    "original_filename": "idea.pdf",
                    "content_type": "application/pdf",
                    "size_bytes": 1234,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
        }
    )


def test_file_data_store_bootstraps_runtime_from_seed(tmp_path) -> None:
    seed_store = FileDataStore(root_dir=tmp_path / "storage" / "seed" / "json", seed_dir=tmp_path / "storage" / "seed" / "json")
    _seed_demo_json(seed_store)

    runtime_store = FileDataStore(
        root_dir=tmp_path / "storage" / "runtime" / "json",
        seed_dir=tmp_path / "storage" / "seed" / "json",
    )

    users = runtime_store.load_dataset("users")

    assert len(users) == 2
    assert (tmp_path / "storage" / "runtime" / "json" / "users.json").exists()
    assert runtime_store.load_dataset("author_watchlist_instruments")[0]["instrument_id"] == "instrument-1"


def test_file_data_store_merges_seed_and_runtime_instruments(tmp_path) -> None:
    seed_store = FileDataStore(root_dir=tmp_path / "storage" / "seed" / "json", seed_dir=tmp_path / "storage" / "seed" / "json")
    seed_store.save_dataset(
        "instruments",
        [
            {
                "id": "instrument-1",
                "ticker": "SBER",
                "name": "Sberbank",
                "board": "TQBR",
                "lot_size": 10,
                "currency": "RUB",
                "instrument_type": "equity",
                "is_active": True,
                "created_at": "2026-03-11T00:00:00+00:00",
                "updated_at": "2026-03-11T00:00:00+00:00",
            },
            {
                "id": "instrument-2",
                "ticker": "GAZP",
                "name": "Gazprom",
                "board": "TQBR",
                "lot_size": 10,
                "currency": "RUB",
                "instrument_type": "equity",
                "is_active": True,
                "created_at": "2026-03-11T00:00:00+00:00",
                "updated_at": "2026-03-11T00:00:00+00:00",
            },
        ],
    )
    runtime_store = FileDataStore(
        root_dir=tmp_path / "storage" / "runtime" / "json",
        seed_dir=tmp_path / "storage" / "seed" / "json",
    )
    runtime_store.save_dataset(
        "instruments",
        [
            {
                "id": "instrument-1",
                "ticker": "SBER",
                "name": "Sberbank Runtime",
                "board": "TQBR",
                "lot_size": 10,
                "currency": "RUB",
                "instrument_type": "equity",
                "is_active": True,
                "created_at": "2026-03-11T00:00:00+00:00",
                "updated_at": "2026-03-11T00:00:00+00:00",
            },
            {
                "id": "instrument-x",
                "ticker": "XTRA",
                "name": "Extra",
                "board": "TQBR",
                "lot_size": 1,
                "currency": "RUB",
                "instrument_type": "equity",
                "is_active": True,
                "created_at": "2026-03-11T00:00:00+00:00",
                "updated_at": "2026-03-11T00:00:00+00:00",
            },
        ],
    )

    merged = runtime_store.load_dataset("instruments")

    assert [item["id"] for item in merged] == ["instrument-1", "instrument-2", "instrument-x"]
    assert merged[0]["name"] == "Sberbank Runtime"


@pytest.mark.asyncio
async def test_file_author_repository_reads_seeded_entities(tmp_path) -> None:
    store = FileDataStore(root_dir=tmp_path / "storage" / "json")
    _seed_demo_json(store)
    repo = FileAuthorRepository(store)

    author = await repo.get_author_by_user_id("user-author")
    assert author is not None

    strategies = await repo.list_author_strategies(author.id)
    recommendations = await repo.list_author_recommendations(author.id)
    watchlist = await repo.list_author_watchlist(author.id)

    assert len(strategies) == 1
    assert strategies[0].title == "Momentum RU"
    assert len(recommendations) == 1
    assert recommendations[0].attachments[0].object_key == "recommendations/rec-1/file.pdf"
    assert [item.id for item in watchlist] == ["instrument-1"]


@pytest.mark.asyncio
async def test_file_author_repository_persists_new_recommendation_and_attachments(tmp_path) -> None:
    store = FileDataStore(root_dir=tmp_path / "storage" / "json")
    _seed_demo_json(store)
    repo = FileAuthorRepository(store)
    author = await repo.get_author_by_user_id("user-author")
    assert author is not None

    recommendation = await create_author_recommendation(
        repo,
        author,
        RecommendationFormData(
            strategy_id="strategy-1",
            kind=RecommendationKind.NEW_IDEA,
            status=RecommendationStatus.DRAFT,
            title="Новая идея",
            summary="summary",
            thesis="thesis",
            market_context="context",
            requires_moderation=False,
            scheduled_for=None,
            legs=[
                StructuredLegFormData(
                    instrument_id="instrument-1",
                    side=TradeSide.BUY,
                    entry_from=Decimal("100.1"),
                    entry_to=Decimal("101.2"),
                    stop_loss=Decimal("98.7"),
                    take_profit_1=Decimal("106.0"),
                    take_profit_2=None,
                    take_profit_3=None,
                    time_horizon="1-2 дня",
                    note="test leg",
                )
            ],
            attachments=[
                IncomingAttachment(
                    filename="new-idea.pdf",
                    content_type="application/pdf",
                    data=b"pdf-data",
                )
            ],
        ),
        uploaded_by_user_id="user-author",
        storage=LocalFilesystemStorage(root_dir=tmp_path / "storage" / "blob"),
    )

    persisted_repo = FileAuthorRepository(store)
    persisted = await persisted_repo.get_author_recommendation(author.id, recommendation.id)

    assert persisted is not None
    assert persisted.title == "Новая идея"
    assert len(persisted.legs) == 1
    assert len(persisted.attachments) == 1
    assert persisted.attachments[0].object_key.startswith(f"recommendations/{recommendation.id}/")
    assert persisted.attachments[0].object_key.endswith("new-idea.pdf")
    assert (tmp_path / "storage" / "blob" / persisted.attachments[0].object_key).exists()


@pytest.mark.asyncio
async def test_file_access_repository_resolves_active_access_and_visible_feed(tmp_path) -> None:
    store = FileDataStore(root_dir=tmp_path / "storage" / "json")
    _seed_demo_json(store)
    repo = FileAccessRepository(store)

    user = await repo.get_user_by_telegram_id(222)
    assert user is not None
    assert await repo.user_has_active_access(user.id) is True

    recommendations = await repo.list_user_visible_recommendations(user_id=user.id)
    assert len(recommendations) == 1
    assert recommendations[0].title == "Покупка SBER"


@pytest.mark.asyncio
async def test_file_public_repository_reads_products_documents_and_payments_scope(tmp_path) -> None:
    store = FileDataStore(root_dir=tmp_path / "storage" / "json")
    _seed_demo_json(store)
    repo = FilePublicRepository(store)

    strategies = await repo.list_public_strategies()
    product = await repo.get_public_product("product-1")
    documents = await repo.list_active_checkout_documents()

    assert len(strategies) == 1
    assert product is not None
    assert product.price_rub == 499
    assert len(documents) == 4


@pytest.mark.asyncio
async def test_file_public_checkout_creates_and_links_lead_source(tmp_path) -> None:
    store = FileDataStore(root_dir=tmp_path / "storage" / "json")
    _seed_demo_json(store)
    repo = FilePublicRepository(store)
    product = await repo.get_public_product("product-1")
    assert product is not None

    result = await create_stub_checkout(
        repo,
        product=product,
        request=CheckoutRequest(
            full_name="Lead User",
            email="lead-new@example.com",
            timezone_name="Europe/Moscow",
            accepted_document_ids=[
                "doc-disclaimer",
                "doc-offer",
                "doc-privacy_policy",
                "doc-payment_consent",
            ],
            lead_source_name="ads_meta",
        ),
    )

    refreshed = FilePublicRepository(store)
    created_user = await refreshed.find_user_by_email("lead-new@example.com")
    assert created_user is not None
    assert created_user.lead_source is not None
    assert created_user.lead_source.name == "ads_meta"
    assert result.subscription.lead_source is not None
    assert result.subscription.lead_source.name == "ads_meta"
