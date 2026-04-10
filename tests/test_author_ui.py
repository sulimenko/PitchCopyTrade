from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from pitchcopytrade.api.deps.auth import require_author
from pitchcopytrade.api.deps.repositories import get_author_repository
from pitchcopytrade.api.main import create_app
from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Instrument, Strategy
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.enums import InstrumentType, MessageStatus, RiskLevel, StrategyStatus


class FakeAuthorRepository:
    async def list_active_instruments(self):
        return []


def _make_author_user() -> User:
    author = User(id="author-user-1", username="author1", full_name="Alpha Desk", timezone="Europe/Moscow")
    author.author_profile = AuthorProfile(
        id="author-1",
        user_id="author-user-1",
        display_name="Alpha Desk",
        slug="alpha-desk",
        is_active=True,
    )
    return author


def _make_strategy() -> Strategy:
    strategy = Strategy(
        id="strategy-1",
        author_id="author-1",
        slug="momentum-ru",
        title="Momentum RU",
        short_description="desc",
        full_description="full",
        risk_level=RiskLevel.MEDIUM,
        status=StrategyStatus.PUBLISHED,
        min_capital_rub=150000,
        is_public=True,
    )
    strategy.author = _make_author_user().author_profile
    return strategy


def _make_message() -> Message:
    strategy = _make_strategy()
    message = Message(
        id="msg-1",
        author_id="author-1",
        strategy_id=strategy.id,
        kind="idea",
        type="mixed",
        status="published",
        moderation="direct",
        title="Покупка SBER",
        comment="Сильный спрос",
        deliver=["strategy"],
        channel=["telegram", "miniapp"],
        text={"body": "<p>Сильный спрос</p>", "plain": "Сильный спрос"},
        documents=[],
        deals=[],
        created=datetime(2026, 3, 12, tzinfo=timezone.utc),
        updated=datetime(2026, 3, 12, tzinfo=timezone.utc),
    )
    message.strategy = strategy
    return message


def _build_client(user: User) -> TestClient:
    app = create_app()

    async def override_author():
      return user

    async def override_repository():
      yield FakeAuthorRepository()

    app.dependency_overrides[require_author] = override_author
    app.dependency_overrides[get_author_repository] = override_repository
    return TestClient(app)


def test_author_dashboard_renders_message_cards(monkeypatch) -> None:
    user = _make_author_user()
    message = _make_message()
    strategy = message.strategy
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
    call_args: list[tuple[int, bool]] = []

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_workspace_stats", lambda _repository, _author: _async_return(type("Stats", (), {
        "strategies_total": 1,
        "messages_total": 1,
        "draft_messages": 0,
        "live_messages": 1,
    })()))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _repository, _author: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_recommendations", lambda _repository, _author: _async_return([message]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_watchlist", lambda _repository, _author: _async_return([instrument]))
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.list_active_instruments",
        lambda _repository: _async_return([instrument]),
    )

    async def fake_build_instrument_payloads(items, allow_live_fetch=True):
        call_args.append((len(items), allow_live_fetch))
        return [
            {"id": item.id, "ticker": item.ticker, "name": item.name, "board": item.board, "currency": item.currency}
            for item in items
        ]

    monkeypatch.setattr("pitchcopytrade.api.routes.author.build_instrument_payloads", fake_build_instrument_payloads)

    with _build_client(user) as client:
        response = client.get("/author/dashboard")

        assert response.status_code == 200
        assert "Последние сообщения" in response.text
        assert "Покупка SBER" in response.text
        assert "Сообщения" in response.text
        assert 'id="composer-dock"' in response.text
        assert 'data-composer-dock-toggle' in response.text
        assert "author-editor-composer" in response.text
        assert "dashboard-message-modal" not in response.text
        assert "message_modal_url" not in response.text
        assert call_args == [(1, False)]
        assert 'fetch("/api/instruments"' in response.text
        assert "window.PCTAuthorInstrumentState" in response.text


def test_author_dashboard_avoids_live_quote_provider(monkeypatch) -> None:
    user = _make_author_user()
    message = _make_message()
    strategy = message.strategy
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

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_workspace_stats", lambda _repository, _author: _async_return(type("Stats", (), {
        "strategies_total": 1,
        "messages_total": 1,
        "draft_messages": 0,
        "live_messages": 1,
    })()))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _repository, _author: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_recommendations", lambda _repository, _author: _async_return([message]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_watchlist", lambda _repository, _author: _async_return([instrument]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _repository: _async_return([instrument]))

    def fail_on_live_fetch(**_kwargs):
        raise AssertionError("live quote provider should not be called on author dashboard")

    monkeypatch.setattr("pitchcopytrade.services.instruments.httpx.AsyncClient", fail_on_live_fetch)

    with _build_client(user) as client:
        response = client.get("/author/dashboard")

        assert response.status_code == 200
        assert "Последние сообщения" in response.text
        assert "author-editor-composer" in response.text
        assert 'fetch("/api/instruments"' in response.text
        assert "window.PCTAuthorInstrumentState" in response.text


def test_author_editor_is_message_centric(monkeypatch) -> None:
    user = _make_author_user()
    strategy = _make_strategy()
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
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _repository, _author: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _repository: _async_return([instrument]))

    with _build_client(user) as client:
        response = client.get("/author/messages/new")

        assert response.status_code == 200
        assert "Новое сообщение" in response.text
        assert "История сообщений" in response.text
        assert "Сделка" in response.text
        assert 'id="composer-dock"' in response.text
        assert 'data-composer-default-open="1"' in response.text
        assert 'id="block-text"' in response.text
        assert 'id="block-documents"' in response.text
        assert 'id="block-deal"' in response.text
        assert 'id="block-history"' in response.text
        assert "author-preview-telegram" in response.text
        assert "message_render_contract" not in response.text
        assert "История сообщений и composer вынесены в dock" in response.text
        assert "Новое сообщение" in response.text
        assert 'data-message-title-hidden' in response.text
        assert 'name="summary"' not in response.text
        assert 'name="thesis"' not in response.text
        assert 'name="market_context"' not in response.text
        assert "remove_attachment_ids\" value=\"\"" not in response.text
        assert "Заметка для модерации" not in response.text
        assert "Предпросмотр и отправка" not in response.text
        assert "publishing" not in response.text
        assert 'type="submit" name="publish_block"' not in response.text
        assert "author-picker-modal" not in response.text
        assert "instrument-autocomplete" in response.text
        assert "structuredPrice && !String(structuredPrice.value || \"\").trim() && item.last_price != null" in response.text
        assert "Отправить сообщение" in response.text
        assert "Buy / Sell" not in response.text
        assert 'type="radio"' in response.text
        assert 'name="structured_side"' in response.text
        assert 'value="buy"' in response.text
        assert 'value="sell"' in response.text
        assert 'id="side-buy"' in response.text
        assert 'id="side-sell"' in response.text
        assert 'for="side-buy" class="side-toggle-label is-buy"' in response.text
        assert 'for="side-sell" class="side-toggle-label is-sell"' in response.text
        assert "side-toggle-option" not in response.text
        assert response.text.count('class="deal-row"') >= 5
        assert 'id="author-history-grid" class="pct-tabulator"' in response.text
        assert "author-history-table" not in response.text
        assert "new Tabulator(" in response.text
        assert 'maxHeight: "400px"' in response.text
        assert 'height: historyData.length > 0 ? "300px" : undefined' not in response.text
        assert "name=\"structured_tp\"" in response.text
        assert "name=\"structured_sl\"" in response.text
        assert 'title: "Превью"' in response.text
        assert "min-width: 140px" not in response.text
        assert "align-self: flex-start" not in response.text
        assert 'width: 100%;' in response.text
        assert "rows=\"14\"" in response.text
        assert "rows=\"2\"" in response.text
        assert "composer-dock-frame" not in response.text
        assert 'data-preview-modal' in response.text
        assert 'data-preview-body' in response.text
        assert 'data-confirm-submit' in response.text
        assert "showModal()" in response.text
        assert "author-preview-telegram" in response.text
        assert "PREVIEW_DIVIDER" in response.text
        assert "PREVIEW_KIND_ICONS" in response.text
        assert 'fetch("/api/instruments"' in response.text
        assert "window.PCTAuthorInstrumentState" in response.text


def test_author_message_create_returns_422_on_missing_strategy(monkeypatch) -> None:
    user = _make_author_user()
    instrument = Instrument(
        id="instrument-1",
        ticker="GAZP",
        name="Gazprom",
        board="TQBR",
        lot_size=10,
        currency="RUB",
        instrument_type=InstrumentType.EQUITY,
        is_active=True,
    )
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _repository, _author: _async_return([]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _repository: _async_return([instrument]))
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.build_instrument_payloads",
        lambda items, allow_live_fetch=True: _async_return([{"id": item.id, "ticker": item.ticker, "name": item.name} for item in items]),
    )
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_recommendations", lambda _repository, _author: _async_return([]))

    with _build_client(user) as client:
        response = client.post(
            "/author/messages",
            data={
                "strategy_id": "",
                "message_type": "deal",
                "structured_instrument_id": instrument.id,
                "structured_instrument_query": instrument.ticker,
                "structured_instrument_ticker": instrument.ticker,
                "structured_instrument_name": instrument.name,
                "structured_side": "buy",
                "structured_price": "120",
                "structured_quantity": "100",
                "structured_tp": "130",
                "structured_sl": "110",
                "structured_note": "Проверка",
                "embedded": "1",
            },
        )

        assert response.status_code == 422
        assert "Выберите стратегию автора" in response.text
        assert 'value="GAZP"' in response.text
        assert 'value="Gazprom"' in response.text
        assert 'value="120"' in response.text
        assert 'value="100"' in response.text
        assert 'value="130"' in response.text
        assert 'value="110"' in response.text
        assert 'Проверка' in response.text


def test_author_message_list_omits_inline_form(monkeypatch) -> None:
    user = _make_author_user()
    message = _make_message()
    strategy = message.strategy
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_recommendations", lambda _repository, _author: _async_return([message]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _repository, _author: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _repository: _async_return([]))
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.build_instrument_payloads",
        lambda items, allow_live_fetch=True: _async_return([]),
    )

    with _build_client(user) as client:
        response = client.get("/author/messages")

        assert response.status_code == 200
        assert "Сообщения автора" in response.text
        assert "inline-recommendation-form" not in response.text
        assert "Новое сообщение" in response.text
        assert 'id="composer-dock"' in response.text
        assert "author-editor-composer" in response.text
        assert "composer-dock-frame" not in response.text


def test_author_draft_message_edit_flow(monkeypatch) -> None:
    user = _make_author_user()
    strategy = _make_strategy()
    draft_message = _make_message()
    draft_message.status = MessageStatus.DRAFT.value
    draft_message.title = "Черновик SBER"
    draft_message.text = {"body": "<p>Старый текст</p>", "plain": "Старый текст"}
    draft_message.strategy = strategy

    async def fake_list_messages(_repository, _author):
        return [draft_message]

    async def fake_get_message(_repository, _author, _message_id):
        assert _message_id == draft_message.id
        return draft_message

    async def fake_list_strategies(_repository, _author):
        return [strategy]

    async def fake_list_instruments(_repository):
        return []

    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_recommendations", fake_list_messages)
    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_recommendation", fake_get_message)
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", fake_list_strategies)
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", fake_list_instruments)
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.build_instrument_payloads",
        lambda items, allow_live_fetch=True: _async_return([]),
    )

    with _build_client(user) as client:
        response = client.get(f"/author/messages/{draft_message.id}/edit")

        assert response.status_code == 200
        assert "Редактирование сообщения" in response.text
        assert 'action="/author/messages/' in response.text
        assert draft_message.title in response.text
        assert 'data-composer-default-open="1"' in response.text
        assert 'name="message_text"' in response.text
        assert "Доставка" in response.text
        assert "Каналы" not in response.text


def test_author_message_edit_dock_has_new_reset_link(monkeypatch) -> None:
    user = _make_author_user()
    strategy = _make_strategy()
    draft_message = _make_message()
    draft_message.status = MessageStatus.DRAFT.value
    draft_message.strategy = strategy

    async def fake_get_message(_repository, _author, _message_id):
        assert _message_id == draft_message.id
        return draft_message

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_recommendation", fake_get_message)
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_recommendations", lambda _repository, _author: _async_return([draft_message]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _repository, _author: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _repository: _async_return([]))
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.build_instrument_payloads",
        lambda items, allow_live_fetch=True: _async_return([]),
    )

    with _build_client(user) as client:
        response = client.get(f"/author/messages/{draft_message.id}/edit")

        assert response.status_code == 200
        assert "+ Новое" in response.text
        assert 'href="/author/messages"' in response.text
        assert "composer-dock-mode is-edit" in response.text


def test_author_document_message_edit_preserves_existing_documents(monkeypatch) -> None:
    user = _make_author_user()
    strategy = _make_strategy()
    document_message = _make_message()
    document_message.status = MessageStatus.DRAFT.value
    document_message.type = "document"
    document_message.text = {"body": "", "plain": "", "title": "Idea PDF"}
    document_message.documents = [
        {
            "id": "doc-1",
            "name": "idea.pdf",
            "title": "idea.pdf",
            "type": "application/pdf",
            "size": 8,
            "storage": "local",
            "key": "messages/msg-1/idea.pdf",
            "hash": "deadbeef",
        }
    ]
    document_message.strategy = strategy

    async def fake_get_message(_repository, _author, _message_id):
        assert _message_id == document_message.id
        return document_message

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_recommendation", fake_get_message)
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_recommendations", lambda _repository, _author: _async_return([document_message]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _repository, _author: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _repository: _async_return([]))
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.build_instrument_payloads",
        lambda items, allow_live_fetch=True: _async_return([]),
    )

    with _build_client(user) as client:
        response = client.get(f"/author/messages/{document_message.id}/edit")

        assert response.status_code == 200
        assert 'value="document"' in response.text
        assert "1 файлов" in response.text
        assert "idea.pdf" in response.text
        assert "document_caption" in response.text


async def _async_return(value):
    return value
