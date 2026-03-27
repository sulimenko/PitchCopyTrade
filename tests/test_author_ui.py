from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from pitchcopytrade.api.deps.auth import require_author
from pitchcopytrade.api.deps.repositories import get_author_repository
from pitchcopytrade.api.main import create_app
from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Instrument, Strategy
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.enums import InstrumentType, RiskLevel, StrategyStatus


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

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_workspace_stats", lambda _repository, _author: _async_return(type("Stats", (), {
        "strategies_total": 1,
        "messages_total": 1,
        "draft_messages": 0,
        "live_messages": 1,
    })()))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _repository, _author: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_recommendations", lambda _repository, _author: _async_return([message]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_watchlist", lambda _repository, _author: _async_return([instrument]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.build_instrument_payloads", lambda items: _async_return([{"id": item.id, "ticker": item.ticker, "name": item.name, "board": item.board, "currency": item.currency} for item in items]))

    with _build_client(user) as client:
        response = client.get("/author/dashboard")

        assert response.status_code == 200
        assert "Последние сообщения" in response.text
        assert "Покупка SBER" in response.text
        assert "Сообщения" in response.text


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
        response = client.get("/author/messages/new?embedded=1")

        assert response.status_code == 200
        assert "Новое сообщение" in response.text
        assert "Тип сообщения" in response.text
        assert "message_type" in response.text
        assert "Заметка для модерации" not in response.text


def test_author_message_list_omits_inline_form(monkeypatch) -> None:
    user = _make_author_user()
    message = _make_message()
    strategy = message.strategy
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_recommendations", lambda _repository, _author: _async_return([message]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _repository, _author: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _repository: _async_return([]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.build_instrument_payloads", lambda items: _async_return([]))

    with _build_client(user) as client:
        response = client.get("/author/messages")

        assert response.status_code == 200
        assert "Сообщения автора" in response.text
        assert "inline-recommendation-form" not in response.text
        assert "Новое сообщение" in response.text


async def _async_return(value):
    return value
