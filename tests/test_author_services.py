from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from io import BytesIO
from unittest.mock import AsyncMock

import pytest
from starlette.datastructures import Headers, UploadFile

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Instrument, Strategy, SubscriptionProduct
from pitchcopytrade.db.models.commerce import Subscription
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.services.author import (
    RecommendationFormData,
    IncomingAttachment,
    add_author_watchlist_instrument,
    build_recommendation_form_data,
    create_author_recommendation,
    normalize_attachment_uploads,
    remove_recommendation_attachments,
    search_author_watchlist_candidates,
    update_author_recommendation,
)
from pitchcopytrade.services import author as author_service
from pitchcopytrade.db.models.enums import (
    BillingPeriod,
    InstrumentType,
    ProductType,
    MessageKind,
    MessageStatus,
    MessageType,
    RiskLevel,
    StrategyStatus,
    SubscriptionStatus,
    UserStatus,
)
from pitchcopytrade.repositories.author import FileAuthorRepository
from pitchcopytrade.repositories.file_store import FileDataStore
from pitchcopytrade.services.notifications import deliver_message_notifications_file
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


@pytest.mark.asyncio
async def test_create_author_recommendation_stores_canonical_attachment_documents(tmp_path) -> None:
    class DummyRepository:
        def __init__(self) -> None:
            self.added = None
            self.flushed = 0
            self.committed = 0
            self.refreshed = 0

        def add(self, entity) -> None:
            self.added = entity

        async def flush(self) -> None:
            self.flushed += 1

        async def commit(self) -> None:
            self.committed += 1

        async def refresh(self, entity) -> None:
            self.refreshed += 1

    author = AuthorProfile(
        id="author-1",
        user_id="user-1",
        display_name="Desk",
        slug="desk",
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
    storage = LocalFilesystemStorage(root_dir=tmp_path / "storage")
    data = RecommendationFormData(
        strategy_id="strategy-1",
        kind=MessageKind.IDEA,
        status=MessageStatus.DRAFT,
        title="Документ",
        deliver=["strategy"],
        channel=["telegram"],
        moderation="required",
        message_type=MessageType.DOCUMENT,
        text_body=None,
        text_plain=None,
        documents=[],
        deals=[],
        schedule=None,
        published=None,
        archived=None,
        requires_moderation=False,
        scheduled_for=None,
        legs=[],
        attachments=[
            IncomingAttachment(
                filename="idea.pdf",
                content_type="application/pdf",
                data=b"pdf-data",
            )
        ],
        message_mode="document",
        message_text="",
        document_caption="",
        structured_instrument_id="instrument-1",
        structured_instrument_ticker=instrument.ticker,
        structured_instrument_name=instrument.name,
        structured_instrument_board=instrument.board,
        structured_instrument_currency=instrument.currency,
        structured_instrument_lot=instrument.lot_size,
        structured_side="buy",
        structured_price=None,
        structured_quantity=None,
        structured_amount=None,
        structured_note=None,
    )

    message = await create_author_recommendation(
        DummyRepository(),
        author,
        data,
        uploaded_by_user_id=author.user_id,
        storage=storage,
    )

    assert message.type == MessageType.DOCUMENT.value
    assert len(message.documents) == 1
    document = message.documents[0]
    assert document["name"] == "idea.pdf"
    assert document["title"] == "idea.pdf"
    assert document["type"] == "application/pdf"
    assert document["storage"] == "local"
    assert document["key"].startswith("messages/")
    assert document["hash"] == hashlib.sha256(b"pdf-data").hexdigest()
    assert storage.download_bytes(str(document["key"])) == b"pdf-data"


@pytest.mark.asyncio
async def test_create_author_recommendation_auto_generates_title_from_text() -> None:
    class DummyRepository:
        def __init__(self) -> None:
            self.added = None
            self.flushed = 0
            self.committed = 0
            self.refreshed = 0

        def add(self, entity) -> None:
            self.added = entity

        async def flush(self) -> None:
            self.flushed += 1

        async def commit(self) -> None:
            self.committed += 1

        async def refresh(self, entity) -> None:
            self.refreshed += 1

    author = AuthorProfile(
        id="author-1",
        user_id="user-1",
        display_name="Desk",
        slug="desk",
        is_active=True,
    )
    data = RecommendationFormData(
        strategy_id="strategy-1",
        kind=MessageKind.IDEA,
        status=MessageStatus.DRAFT,
        title="",
        deliver=["strategy"],
        channel=["telegram"],
        moderation="required",
        message_type=MessageType.TEXT,
        text_body="<p>Сильный спрос на SBER после отчета</p>",
        text_plain="Сильный спрос на SBER после отчета",
        documents=[],
        deals=[],
        schedule=None,
        published=None,
        archived=None,
        requires_moderation=False,
        scheduled_for=None,
        legs=[],
        attachments=[],
        message_mode="text",
        message_text="Сильный спрос на SBER после отчета",
        document_caption="",
    )

    message = await create_author_recommendation(
        DummyRepository(),
        author,
        data,
        uploaded_by_user_id=author.user_id,
    )

    assert message.title.startswith("Сильный спрос на SBER")


@pytest.mark.asyncio
async def test_update_author_recommendation_keeps_existing_documents() -> None:
    class DummyRepository:
        async def flush(self) -> None:
            return None

        async def commit(self) -> None:
            return None

        async def refresh(self, entity) -> None:
            return None

    author = AuthorProfile(
        id="author-1",
        user_id="user-1",
        display_name="Desk",
        slug="desk",
        is_active=True,
    )
    existing_document = {
        "id": "doc-1",
        "name": "idea.pdf",
        "title": "idea.pdf",
        "type": "application/pdf",
        "size": 8,
        "storage": "local",
        "key": "messages/msg-1/idea.pdf",
        "hash": "deadbeef",
    }
    message = Message(
        id="msg-1",
        strategy_id="strategy-1",
        author_id=author.id,
        thread="msg-1",
        kind=MessageKind.IDEA.value,
        type=MessageType.DOCUMENT.value,
        status=MessageStatus.DRAFT.value,
        moderation="required",
        title="Документ",
        deliver=["strategy"],
        channel=["telegram"],
        text={"body": "", "plain": "", "title": "Документ"},
        documents=[existing_document],
        deals=[],
    )
    data = RecommendationFormData(
        strategy_id="strategy-1",
        kind=MessageKind.IDEA,
        status=MessageStatus.DRAFT,
        title="Документ",
        deliver=["strategy"],
        channel=["telegram"],
        moderation="required",
        message_type=MessageType.DOCUMENT,
        text_body=None,
        text_plain=None,
        documents=[existing_document],
        deals=[],
        schedule=None,
        published=None,
        archived=None,
        requires_moderation=False,
        scheduled_for=None,
        legs=[],
        attachments=[],
        message_mode="document",
        message_text="",
        document_caption="",
    )

    updated = await update_author_recommendation(
        DummyRepository(),
        author,
        message,
        data,
        uploaded_by_user_id=author.user_id,
    )

    assert updated.documents == [existing_document]


@pytest.mark.asyncio
async def test_create_author_recommendation_applies_publish_state_before_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyRepository:
        def __init__(self) -> None:
            self.added = None

        def add(self, entity) -> None:
            self.added = entity

        async def flush(self) -> None:
            return None

        async def commit(self) -> None:
            return None

        async def refresh(self, entity) -> None:
            return None

    author = AuthorProfile(
        id="author-1",
        user_id="user-1",
        display_name="Desk",
        slug="desk",
        is_active=True,
    )
    data = RecommendationFormData(
        strategy_id="strategy-1",
        kind=MessageKind.IDEA,
        status=MessageStatus.PUBLISHED,
        title="Покупка SBER",
        deliver=["strategy"],
        channel=["telegram"],
        moderation="required",
        message_type=MessageType.TEXT,
        text_body="<p>Сильный спрос</p>",
        text_plain="Сильный спрос",
        documents=[],
        deals=[],
        schedule=None,
        published=None,
        archived=None,
        requires_moderation=False,
        scheduled_for=None,
        legs=[],
        attachments=[],
        message_mode="text",
        message_text="Сильный спрос",
        document_caption="",
    )

    order: list[str] = []
    original_apply = author_service._apply_publish_state
    original_validate = author_service._validate_message_contract

    def fake_apply_publish_state(message) -> None:
        order.append("apply")
        original_apply(message)

    def fake_validate_message_contract(message) -> None:
        order.append("validate")
        assert message.published is not None
        original_validate(message)

    monkeypatch.setattr(author_service, "_apply_publish_state", fake_apply_publish_state)
    monkeypatch.setattr(author_service, "_validate_message_contract", fake_validate_message_contract)

    message = await create_author_recommendation(
        DummyRepository(),
        author,
        data,
        uploaded_by_user_id=author.user_id,
    )

    assert order[:2] == ["apply", "validate"]
    assert message.status == MessageStatus.PUBLISHED.value
    assert message.published is not None


@pytest.mark.asyncio
async def test_update_author_recommendation_applies_publish_state_before_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyRepository:
        async def flush(self) -> None:
            return None

        async def commit(self) -> None:
            return None

        async def refresh(self, entity) -> None:
            return None

    author = AuthorProfile(
        id="author-1",
        user_id="user-1",
        display_name="Desk",
        slug="desk",
        is_active=True,
    )
    message = Message(
        id="msg-1",
        strategy_id="strategy-1",
        author_id=author.id,
        thread="msg-1",
        kind=MessageKind.IDEA.value,
        type=MessageType.TEXT.value,
        status=MessageStatus.DRAFT.value,
        moderation="required",
        title="Покупка SBER",
        deliver=["strategy"],
        channel=["telegram"],
        text={"body": "<p>Сильный спрос</p>", "plain": "Сильный спрос"},
        documents=[],
        deals=[],
    )
    data = RecommendationFormData(
        strategy_id="strategy-1",
        kind=MessageKind.IDEA,
        status=MessageStatus.PUBLISHED,
        title="Покупка SBER",
        deliver=["strategy"],
        channel=["telegram"],
        moderation="required",
        message_type=MessageType.TEXT,
        text_body="<p>Сильный спрос</p>",
        text_plain="Сильный спрос",
        documents=[],
        deals=[],
        schedule=None,
        published=None,
        archived=None,
        requires_moderation=False,
        scheduled_for=None,
        legs=[],
        attachments=[],
        message_mode="text",
        message_text="Сильный спрос",
        document_caption="",
    )

    order: list[str] = []
    original_apply = author_service._apply_publish_state
    original_validate = author_service._validate_message_contract

    def fake_apply_publish_state(message_obj) -> None:
        order.append("apply")
        original_apply(message_obj)

    def fake_validate_message_contract(message_obj) -> None:
        order.append("validate")
        assert message_obj.published is not None
        original_validate(message_obj)

    monkeypatch.setattr(author_service, "_apply_publish_state", fake_apply_publish_state)
    monkeypatch.setattr(author_service, "_validate_message_contract", fake_validate_message_contract)

    updated = await update_author_recommendation(
        DummyRepository(),
        author,
        message,
        data,
        uploaded_by_user_id=author.user_id,
    )

    assert order[:2] == ["apply", "validate"]
    assert updated.status == MessageStatus.PUBLISHED.value
    assert updated.published is not None


def test_build_recommendation_form_data_builds_canonical_deal() -> None:
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
    payload = build_recommendation_form_data(
        strategy_id="strategy-1",
        kind_value="new_idea",
        status_value="draft",
        title="Покупка SBER",
        structured_instrument_id="instrument-1",
        structured_side_value="buy",
        structured_price="101.5",
        structured_quantity="2",
        structured_tp="110.0",
        structured_sl="98.0",
        structured_note="Основной вход",
        author_requires_moderation=False,
        scheduled_for="",
        allowed_strategy_ids={"strategy-1"},
        allowed_instrument_ids={"instrument-1"},
        selected_instrument=instrument,
        attachments=[],
    )

    assert len(payload.deals) == 1
    assert payload.deals[0]["instrument"] == "Sberbank"
    assert payload.deals[0]["ticker"] == "SBER"
    assert payload.deals[0]["side"] == "buy"
    assert payload.deals[0]["price"] == "101.5"
    assert payload.deals[0]["quantity"] == "2"
    assert payload.deals[0]["amount"] == "203"
    assert payload.deals[0]["take_profit_1"] == "110"
    assert payload.deals[0]["stop_loss"] == "98"
    assert payload.kind == MessageKind.IDEA
    assert payload.status == MessageStatus.DRAFT
    assert payload.message_type == MessageType.DEAL


def test_recommendation_form_values_prefers_structured_instrument_id() -> None:
    message = Message(
        id="msg-1",
        strategy_id="strategy-1",
        author_id="author-1",
        thread="msg-1",
        kind=MessageKind.IDEA.value,
        type=MessageType.DEAL.value,
        status=MessageStatus.DRAFT.value,
        moderation="required",
        title="Покупка SBER",
        deliver=["strategy"],
        channel=["telegram"],
        text={"body": "", "plain": "", "title": "Покупка SBER"},
        documents=[],
        deals=[
            {
                "instrument": "Sberbank",
                "instrument_id": "instrument-1",
                "ticker": "SBER",
                "name": "Sberbank",
                "side": "buy",
                "price": "101.5",
            }
        ],
    )

    values = author_service.recommendation_form_values(message)

    assert values["structured_instrument_id"] == "instrument-1"
    assert values["structured_instrument_query"] == "SBER"
    assert values["structured_instrument_name"] == "Sberbank"


def test_build_recommendation_form_data_requires_content() -> None:
    with pytest.raises(ValueError, match="Для mixed message нужен хотя бы один блок контента"):
        build_recommendation_form_data(
            strategy_id="strategy-1",
            kind_value="new_idea",
            status_value="draft",
            title="Покупка SBER",
            author_requires_moderation=False,
            scheduled_for="",
            allowed_strategy_ids={"strategy-1"},
            allowed_instrument_ids={"instrument-1"},
            attachments=[],
        )


def test_build_recommendation_form_data_allows_text_only_with_default_side_selected() -> None:
    payload = build_recommendation_form_data(
        strategy_id="strategy-1",
        kind_value="new_idea",
        status_value="draft",
        title="Комментарий по рынку",
        message_text="Свободное текстовое сообщение",
        structured_side_value="buy",
        author_requires_moderation=False,
        scheduled_for="",
        allowed_strategy_ids={"strategy-1"},
        allowed_instrument_ids={"instrument-1"},
        attachments=[],
    )

    assert payload.message_type == MessageType.TEXT
    assert payload.text_body == "Свободное текстовое сообщение"
    assert payload.deals == []


def test_build_recommendation_form_data_allows_document_only_with_default_side_selected() -> None:
    payload = build_recommendation_form_data(
        strategy_id="strategy-1",
        kind_value="new_idea",
        status_value="draft",
        title="OnePager",
        document_caption="OnePager без текста",
        structured_side_value="buy",
        documents=[
            {
                "id": "doc-1",
                "name": "onepager.pdf",
                "type": "application/pdf",
                "size": 128,
                "key": "messages/msg-1/onepager.pdf",
            }
        ],
        author_requires_moderation=False,
        scheduled_for="",
        allowed_strategy_ids={"strategy-1"},
        allowed_instrument_ids={"instrument-1"},
        attachments=[],
    )

    assert payload.message_type == MessageType.DOCUMENT
    assert len(payload.documents) == 1
    assert payload.deals == []


def test_build_recommendation_form_data_rejects_missing_deal_fields() -> None:
    with pytest.raises(ValueError, match="Для structured message нужны инструмент, цена и количество."):
        build_recommendation_form_data(
            strategy_id="strategy-1",
            kind_value="new_idea",
            status_value="draft",
            title="Покупка SBER",
            structured_instrument_id="instrument-1",
            structured_side_value="buy",
            author_requires_moderation=False,
            scheduled_for="",
            allowed_strategy_ids={"strategy-1"},
            allowed_instrument_ids={"instrument-1"},
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
    recommendation = Message(
        id="rec-1",
        strategy_id="strategy-1",
        author_id="author-1",
        thread="rec-1",
        kind=MessageKind.IDEA.value,
        type=MessageType.DOCUMENT.value,
        status=MessageStatus.DRAFT.value,
        moderation="required",
        documents=[
            {
                "id": "att-1",
                "object_key": "messages/rec-1/file.pdf",
                "original_filename": "idea.pdf",
                "content_type": "application/pdf",
                "size_bytes": 8,
            }
        ],
    )
    storage = LocalFilesystemStorage(root_dir=tmp_path / "storage" / "blob")
    storage.upload_bytes("messages/rec-1/file.pdf", b"pdf-data", "application/pdf")

    await remove_recommendation_attachments(repository, recommendation, ["att-1"], storage=storage)

    assert recommendation.documents == []
    assert repository.deleted == []
    assert not (tmp_path / "storage" / "blob" / "messages" / "rec-1" / "file.pdf").exists()


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

    published = RecommendationFormData(
        strategy_id="strategy-1",
        kind=MessageKind.IDEA,
        status=MessageStatus.PUBLISHED,
        title="Покупка SBER",
        deliver=["strategy"],
        channel=["telegram"],
        moderation="required",
        message_type=MessageType.TEXT,
        text_body="<p>Сильный спрос</p>",
        text_plain="Сильный спрос",
        documents=[],
        deals=[],
        schedule=datetime(2026, 3, 12, 10, 0, tzinfo=timezone.utc),
        published=datetime(2026, 3, 12, 10, 0, tzinfo=timezone.utc),
        requires_moderation=False,
        scheduled_for=datetime(2026, 3, 12, 10, 0, tzinfo=timezone.utc),
        legs=[],
        attachments=[],
    )
    recommendation = await create_author_recommendation(repository, author, published, uploaded_by_user_id=author.user_id)
    assert recommendation.status == MessageStatus.PUBLISHED.value
    assert recommendation.published is not None

    fake_bot = type(
        "FakeBot",
        (),
        {
            "send_message": AsyncMock(),
            "session": type("FakeSession", (), {"close": AsyncMock()})(),
        },
    )()
    await deliver_message_notifications_file(
        repository.graph,
        store,
        recommendation,
        fake_bot,
        trigger="author_publish_smoke",
    )

    fake_bot.send_message.assert_awaited_once()
    chat_id, text = fake_bot.send_message.await_args.args
    assert chat_id == 777000
    assert "Покупка SBER" in text

    reloaded = FileAuthorRepository(store)
    delivery_events = [
        item
        for item in reloaded.graph.audit_events.values()
        if item.action == "notification.delivery" and item.entity_id == recommendation.id
    ]
    assert len(delivery_events) == 1
    assert delivery_events[0].payload["recipient_count"] == 1
    assert delivery_events[0].payload["trigger"] == "author_publish_smoke"
