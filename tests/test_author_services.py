from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import AsyncMock

import pytest
from starlette.datastructures import FormData, Headers, UploadFile

from pitchcopytrade.api.routes.author import _deliver_author_publish_notifications
from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Instrument, Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import Subscription
from pitchcopytrade.services.author import (
    RecommendationFormData,
    StructuredLegFormData,
    add_author_watchlist_instrument,
    build_leg_rows_from_form,
    build_recommendation_form_data,
    create_author_recommendation,
    normalize_attachment_uploads,
    remove_recommendation_attachments,
    search_author_watchlist_candidates,
    update_author_recommendation,
)
from pitchcopytrade.db.models.content import Recommendation, RecommendationAttachment
from pitchcopytrade.db.models.enums import (
    BillingPeriod,
    InstrumentType,
    ProductType,
    RecommendationKind,
    RecommendationStatus,
    RiskLevel,
    StrategyStatus,
    SubscriptionStatus,
    TradeSide,
    UserStatus,
)
from pitchcopytrade.repositories.author import FileAuthorRepository
from pitchcopytrade.repositories.file_store import FileDataStore
from pitchcopytrade.storage.local import LocalFilesystemStorage


@pytest.mark.asyncio
async def test_normalize_attachment_uploads_accepts_pdf() -> None:
    upload = UploadFile(file=BytesIO(b"pdf-data"), filename="idea.pdf", headers=Headers({"content-type": "application/pdf"}))

    items = await normalize_attachment_uploads([upload])

    assert len(items) == 1
    assert items[0].filename == "idea.pdf"
    assert items[0].content_type == "application/pdf"


@pytest.mark.asyncio
async def test_normalize_attachment_uploads_rejects_unsupported_type() -> None:
    upload = UploadFile(
        file=BytesIO(b"exe"),
        filename="bad.exe",
        headers=Headers({"content-type": "application/x-msdownload"}),
    )

    with pytest.raises(ValueError, match="Разрешены только PDF"):
        await normalize_attachment_uploads([upload])


def test_build_recommendation_form_data_parses_structured_leg() -> None:
    payload = build_recommendation_form_data(
        strategy_id="strategy-1",
        kind_value="new_idea",
        status_value="draft",
        title="Покупка SBER",
        summary="summary",
        thesis="thesis",
        market_context="context",
        author_requires_moderation=False,
        scheduled_for="",
        allowed_strategy_ids={"strategy-1"},
        allowed_instrument_ids={"instrument-1"},
        leg_rows=[
            {
                "instrument_id": "instrument-1",
                "side": "buy",
                "entry_from": "101.5",
                "entry_to": "102.1",
                "stop_loss": "99.9",
                "take_profit_1": "106.2",
                "take_profit_2": "",
                "take_profit_3": "",
                "time_horizon": "1-3 дня",
                "note": "Основной вход",
            }
        ],
        attachments=[],
    )

    assert len(payload.legs) == 1
    assert payload.legs[0].instrument_id == "instrument-1"
    assert str(payload.legs[0].entry_from) == "101.5"


def test_build_recommendation_form_data_allows_minimal_inline_leg() -> None:
    payload = build_recommendation_form_data(
        strategy_id="strategy-1",
        kind_value="new_idea",
        status_value="draft",
        title="",
        summary="",
        thesis="",
        market_context="",
        author_requires_moderation=False,
        scheduled_for="",
        allowed_strategy_ids={"strategy-1"},
        allowed_instrument_ids={"instrument-1"},
        leg_rows=[
            {
                "instrument_id": "instrument-1",
                "side": "buy",
                "entry_from": "",
                "entry_to": "",
                "stop_loss": "",
                "take_profit_1": "",
                "take_profit_2": "",
                "take_profit_3": "",
                "time_horizon": "",
                "note": "",
            }
        ],
        attachments=[],
    )

    assert payload.kind.value == "new_idea"
    assert payload.legs[0].instrument_id == "instrument-1"
    assert payload.legs[0].entry_from is None
    assert payload.legs[0].take_profit_1 is None


def test_build_leg_rows_from_form_preserves_dynamic_indexes() -> None:
    form = FormData(
        {
            "leg_7_instrument_id": "instrument-7",
            "leg_7_side": "buy",
            "leg_7_entry_from": "101.5",
            "leg_12_instrument_id": "instrument-12",
            "leg_12_side": "sell",
            "leg_12_stop_loss": "99.2",
        }
    )

    rows = build_leg_rows_from_form(form)

    assert [row["row_id"] for row in rows] == ["7", "12"]
    assert rows[0]["instrument_id"] == "instrument-7"
    assert rows[1]["side"] == "sell"


def test_build_recommendation_form_data_requires_at_least_one_leg() -> None:
    with pytest.raises(ValueError, match="Добавьте минимум одну бумагу"):
        build_recommendation_form_data(
            strategy_id="strategy-1",
            kind_value="new_idea",
            status_value="draft",
            title="Покупка SBER",
            summary="summary",
            thesis="thesis",
            market_context="context",
                author_requires_moderation=False,
            scheduled_for="",
            allowed_strategy_ids={"strategy-1"},
            allowed_instrument_ids={"instrument-1"},
            leg_rows=[],
            attachments=[],
        )


def test_build_recommendation_form_data_rejects_unknown_instrument() -> None:
    with pytest.raises(ValueError, match="Leg 1: выберите допустимый инструмент"):
        build_recommendation_form_data(
            strategy_id="strategy-1",
            kind_value="new_idea",
            status_value="draft",
            title="Покупка SBER",
            summary="summary",
            thesis="thesis",
            market_context="context",
                author_requires_moderation=False,
            scheduled_for="",
            allowed_strategy_ids={"strategy-1"},
            allowed_instrument_ids={"instrument-1"},
            leg_rows=[
                {
                    "instrument_id": "bad",
                    "side": "buy",
                    "entry_from": "101.5",
                    "entry_to": "",
                    "stop_loss": "99.9",
                    "take_profit_1": "106.2",
                    "take_profit_2": "",
                    "take_profit_3": "",
                    "time_horizon": "",
                    "note": "",
                }
            ],
            attachments=[],
        )


@pytest.mark.asyncio
async def test_remove_recommendation_attachments_deletes_local_blob(tmp_path) -> None:
    class DummyRepository:
        def __init__(self) -> None:
            self.deleted = []

        async def delete(self, entity) -> None:
            self.deleted.append(entity)

    repository = DummyRepository()
    recommendation = Recommendation(id="rec-1", strategy_id="strategy-1", author_id="author-1")
    attachment = RecommendationAttachment(
        id="att-1",
        recommendation_id="rec-1",
        object_key="recommendations/rec-1/file.pdf",
        original_filename="idea.pdf",
        content_type="application/pdf",
        size_bytes=8,
    )
    recommendation.attachments = [attachment]
    storage = LocalFilesystemStorage(root_dir=tmp_path / "storage" / "blob")
    storage.upload_bytes(attachment.object_key, b"pdf-data", "application/pdf")

    await remove_recommendation_attachments(repository, recommendation, ["att-1"], storage=storage)

    assert recommendation.attachments == []
    assert repository.deleted == [attachment]
    assert not (tmp_path / "storage" / "blob" / "recommendations" / "rec-1" / "file.pdf").exists()


@pytest.mark.asyncio
async def test_search_author_watchlist_candidates_excludes_existing_watchlist() -> None:
    author = type("Author", (), {"id": "author-1"})()
    existing = Instrument(
        id="instrument-1",
        ticker="SBER",
        name="Sberbank",
        board="TQBR",
        lot_size=10,
        currency="RUB",
        instrument_type=InstrumentType.EQUITY,
        is_active=True,
    )
    candidate = Instrument(
        id="instrument-2",
        ticker="GAZP",
        name="Gazprom",
        board="TQBR",
        lot_size=10,
        currency="RUB",
        instrument_type=InstrumentType.EQUITY,
        is_active=True,
    )

    class DummyRepository:
        async def list_author_watchlist(self, author_id: str):
            assert author_id == "author-1"
            return [existing]

        async def list_active_instruments(self):
            return [existing, candidate]

        async def add_author_watchlist_instrument(self, author_id: str, instrument_id: str):
            assert author_id == "author-1"
            assert instrument_id == "instrument-2"
            return candidate

    items = await search_author_watchlist_candidates(DummyRepository(), author, "gaz")

    assert [item.id for item in items] == ["instrument-2"]


@pytest.mark.asyncio
async def test_add_author_watchlist_instrument_raises_for_unknown_instrument() -> None:
    author = type("Author", (), {"id": "author-1"})()

    class DummyRepository:
        async def add_author_watchlist_instrument(self, author_id: str, instrument_id: str):
            assert author_id == "author-1"
            assert instrument_id == "unknown"
            return None

    with pytest.raises(ValueError, match="Инструмент не найден"):
        await add_author_watchlist_instrument(DummyRepository(), author, "unknown")


@pytest.mark.asyncio
async def test_file_mode_smoke_publish_notifies_active_subscriber(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = FileDataStore(root_dir=tmp_path / "runtime", seed_dir=tmp_path / "runtime")
    repository = FileAuthorRepository(store)
    graph = repository.graph

    author_user = User(
        id="author-user-1",
        email="author@example.com",
        username="author1",
        full_name="Author One",
        status=UserStatus.ACTIVE,
        timezone="Europe/Moscow",
    )
    subscriber = User(
        id="subscriber-1",
        email="subscriber@example.com",
        telegram_user_id=777000,
        username="subscriber1",
        full_name="Subscriber One",
        status=UserStatus.ACTIVE,
        timezone="Europe/Moscow",
    )
    author = AuthorProfile(
        id="author-1",
        user_id=author_user.id,
        display_name="Author One",
        slug="author-one",
        is_active=True,
    )
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
    strategy = Strategy(
        id="strategy-1",
        author_id=author.id,
        slug="momentum-ru",
        title="Momentum RU",
        short_description="desc",
        full_description="full",
        risk_level=RiskLevel.MEDIUM,
        status=StrategyStatus.PUBLISHED,
        min_capital_rub=150000,
        is_public=True,
    )
    product = SubscriptionProduct(
        id="product-1",
        product_type=ProductType.STRATEGY,
        slug="momentum-ru-month",
        title="Momentum RU Monthly",
        description="Monthly access",
        strategy_id=strategy.id,
        billing_period=BillingPeriod.MONTH,
        price_rub=4900,
        trial_days=0,
        is_active=True,
        autorenew_allowed=True,
    )
    subscription = Subscription(
        id="subscription-1",
        user_id=subscriber.id,
        product_id=product.id,
        status=SubscriptionStatus.ACTIVE,
        autorenew_enabled=True,
        is_trial=False,
        manual_discount_rub=0,
        start_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )

    for entity in (author_user, subscriber, author, instrument, strategy, product, subscription):
        graph.add(entity)
    graph.save(store)

    repository = FileAuthorRepository(store)
    author = repository.graph.authors["author-1"]

    draft = RecommendationFormData(
        strategy_id="strategy-1",
        kind=RecommendationKind.NEW_IDEA,
        status=RecommendationStatus.DRAFT,
        title="Покупка SBER",
        summary="Сильный спрос",
        thesis="Рост оборотов",
        market_context="Рынок подтверждает импульс",
        requires_moderation=False,
        scheduled_for=None,
        legs=[
            StructuredLegFormData(
                instrument_id="instrument-1",
                side=TradeSide.BUY,
                entry_from=101.5,
                entry_to=None,
                stop_loss=99.9,
                take_profit_1=106.2,
                take_profit_2=None,
                take_profit_3=None,
                time_horizon="1-3 дня",
                note="Основной вход",
            )
        ],
        attachments=[],
    )
    recommendation = await create_author_recommendation(repository, author, draft, uploaded_by_user_id=author.user_id)

    published = RecommendationFormData(
        strategy_id="strategy-1",
        kind=RecommendationKind.NEW_IDEA,
        status=RecommendationStatus.PUBLISHED,
        title="Покупка SBER",
        summary="Сильный спрос",
        thesis="Рост оборотов",
        market_context="Рынок подтверждает импульс",
        requires_moderation=False,
        scheduled_for=None,
        legs=draft.legs,
        attachments=[],
    )
    recommendation = await update_author_recommendation(
        repository,
        recommendation,
        published,
        uploaded_by_user_id=author.user_id,
    )
    assert recommendation.status is RecommendationStatus.PUBLISHED
    assert recommendation.published_at is not None

    fake_bot = type(
        "FakeBot",
        (),
        {
            "send_message": AsyncMock(),
            "session": type("FakeSession", (), {"close": AsyncMock()})(),
        },
    )()
    monkeypatch.setattr("pitchcopytrade.api.routes.author.create_bot", lambda _token: fake_bot)
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "telegram": type(
                    "Telegram",
                    (),
                    {"bot_token": type("Secret", (), {"get_secret_value": lambda self: "token"})()},
                )(),
            },
        )(),
    )

    await _deliver_author_publish_notifications(
        repository=repository,
        author=author,
        recommendation_id=recommendation.id,
        trigger="author_publish_smoke",
    )

    fake_bot.send_message.assert_awaited_once()
    chat_id, text = fake_bot.send_message.await_args.args
    assert chat_id == 777000
    assert "Покупка SBER" in text
    fake_bot.session.close.assert_awaited_once()

    reloaded = FileAuthorRepository(store)
    delivery_events = [
        item
        for item in reloaded.graph.audit_events.values()
        if item.action == "notification.delivery" and item.entity_id == recommendation.id
    ]
    assert len(delivery_events) == 1
    assert delivery_events[0].payload["recipient_count"] == 1
    assert delivery_events[0].payload["trigger"] == "author_publish_smoke"
