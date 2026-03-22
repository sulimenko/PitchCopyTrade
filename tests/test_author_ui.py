from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from pitchcopytrade.api.deps.auth import require_author
from pitchcopytrade.api.main import create_app
from pitchcopytrade.db.models.accounts import AuthorProfile, Role, User
from pitchcopytrade.db.models.catalog import Instrument, Strategy
from pitchcopytrade.db.models.content import Recommendation
from pitchcopytrade.db.models.content import RecommendationAttachment
from pitchcopytrade.db.models.enums import (
    InstrumentType,
    RecommendationKind,
    RecommendationStatus,
    RiskLevel,
    RoleSlug,
    StrategyStatus,
)
from pitchcopytrade.db.session import get_db_session


class FakeAsyncSession:
    async def execute(self, query):
        raise AssertionError("This suite expects monkeypatched service calls")


def _make_author_user() -> User:
    user = User(
        id="author-user-1",
        username="author1",
        email="author@example.com",
        full_name="Author One",
        timezone="Europe/Moscow",
    )
    user.roles = [Role(slug=RoleSlug.AUTHOR, title="Author")]
    user.author_profile = AuthorProfile(
        id="author-1",
        user_id=user.id,
        display_name="Author One",
        slug="author-one",
        is_active=True,
    )
    return user


def _make_strategy() -> Strategy:
    return Strategy(
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


def _make_recommendation() -> Recommendation:
    recommendation = Recommendation(
        id="rec-1",
        strategy_id="strategy-1",
        author_id="author-1",
        kind=RecommendationKind.NEW_IDEA,
        status=RecommendationStatus.DRAFT,
        title="Покупка SBER",
        summary="Краткий комментарий",
    )
    recommendation.strategy = _make_strategy()
    recommendation.legs = []
    recommendation.attachments = []
    recommendation.scheduled_for = None
    recommendation.published_at = None
    return recommendation


def _make_instrument() -> Instrument:
    return Instrument(
        id="instrument-1",
        ticker="SBER",
        name="Sberbank",
        board="TQBR",
        lot_size=10,
        currency="RUB",
        instrument_type=InstrumentType.EQUITY,
        is_active=True,
    )


def _build_client(author_user: User) -> TestClient:
    app = create_app()

    async def override_db_session():
        yield FakeAsyncSession()

    async def override_author():
        return author_user

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[require_author] = override_author
    return TestClient(app)


def test_author_dashboard_renders(monkeypatch) -> None:
    author_user = _make_author_user()
    strategy = _make_strategy()
    recommendation = _make_recommendation()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.get_author_workspace_stats",
        lambda _session, _author: _async_return(
            SimpleNamespace(
                strategies_total=1,
                recommendations_total=3,
                draft_recommendations=2,
                live_recommendations=1,
            )
        ),
    )
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _session, _author: _async_return([strategy]))
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.list_author_recommendations",
        lambda _session, _author: _async_return([recommendation]),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.list_author_watchlist",
        lambda _session, _author: _async_return([_make_instrument()]),
    )
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _session: _async_return([_make_instrument()]))

    with _build_client(author_user) as client:
        response = client.get("/author/dashboard")

        assert response.status_code == 200
        assert "Author One" in response.text
        assert "Momentum RU" in response.text
        assert "Покупка SBER" in response.text
        assert "Наблюдение за бумагами" in response.text
        assert "Поиск и добавление" in response.text
        assert "data-open-recommendation-modal" in response.text


def test_author_strategy_list_renders(monkeypatch) -> None:
    author_user = _make_author_user()
    strategy = _make_strategy()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _repository, _author: _async_return([strategy]))

    with _build_client(author_user) as client:
        response = client.get("/author/strategies")

        assert response.status_code == 200
        assert "порог капитала без открытия редактора" in response.text
        assert "Новая стратегия откроет короткую форму" in response.text
        assert "Momentum RU" in response.text


def test_author_strategy_create_redirects(monkeypatch) -> None:
    author_user = _make_author_user()
    strategy = _make_strategy()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _repository, _author: _async_return([]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.create_author_strategy", lambda _repository, _author, _data: _async_return(strategy))

    with _build_client(author_user) as client:
        response = client.post(
            "/author/strategies",
            data={
                "title": "Momentum RU",
                "slug": "momentum-ru",
                "short_description": "desc",
                "risk_level": "medium",
                "min_capital_rub": "150000",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/author/strategies"


def test_author_strategy_edit_page_renders(monkeypatch) -> None:
    author_user = _make_author_user()
    strategy = _make_strategy()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_strategy", lambda _repository, _author, _strategy_id: _async_return(strategy))

    with _build_client(author_user) as client:
        response = client.get("/author/strategies/strategy-1/edit")

        assert response.status_code == 200
        assert "Редактирование стратегии" in response.text
        assert "Momentum RU" in response.text
        assert "Основное" in response.text
        assert "Действия" in response.text
        assert 'class="staff-content"' in response.text


def test_author_recommendation_list_renders(monkeypatch) -> None:
    author_user = _make_author_user()
    recommendation = _make_recommendation()
    instrument = _make_instrument()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.list_author_recommendations",
        lambda _session, _author: _async_return([recommendation]),
    )
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _session, _author: _async_return([_make_strategy()]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _session: _async_return([instrument]))

    with _build_client(author_user) as client:
        response = client.get("/author/recommendations")

        assert response.status_code == 200
        assert "Рекомендации автора" in response.text
        assert "Покупка SBER" in response.text
        assert "inline-recommendation-form" in response.text
        assert 'id="inline-recommendation-form" hidden' in response.text
        assert 'form="inline-recommendation-form"' in response.text
        assert 'name="kind" value="new_idea"' in response.text
        assert 'name="inline_mode" value="1"' in response.text
        assert 'type="submit" form="inline-recommendation-form"' in response.text
        assert "data-inline-detail" in response.text
        assert 'title="Открыть полный редактор с уже заполненными полями">Детально</button>' in response.text
        assert "inline-shortcut-fields" in response.text
        assert 'title="Создать черновик и вернуться в реестр"' in response.text
        assert "inline-create-hint-row" not in response.text
        assert "Создать добавляет черновик в реестр" not in response.text
        assert "position: fixed" in response.text
        assert "display: contents" not in response.text
        assert "inline-ticker-backdrop" in response.text
        assert "workspace-modal-frame" in response.text


def test_author_watchlist_search_returns_json(monkeypatch) -> None:
    author_user = _make_author_user()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.search_author_watchlist_candidates",
        lambda _repository, _author, query: _async_return(
            [SimpleNamespace(id="instrument-2", ticker="GAZP", name="Gazprom", board="TQBR", source="catalog")]
        ),
    )

    with _build_client(author_user) as client:
        response = client.get("/author/watchlist/search?q=gaz")

        assert response.status_code == 200
        assert response.json()["items"][0]["ticker"] == "GAZP"


def test_author_watchlist_add_returns_updated_list(monkeypatch) -> None:
    author_user = _make_author_user()
    instrument = _make_instrument()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.add_author_watchlist_instrument",
        lambda _repository, _author, _instrument_id: _async_return(instrument),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.list_author_watchlist",
        lambda _repository, _author: _async_return([instrument]),
    )

    with _build_client(author_user) as client:
        response = client.post("/author/watchlist/items", data={"instrument_id": "instrument-1"})

        assert response.status_code == 200
        payload = response.json()
        assert payload["added"]["ticker"] == "SBER"
        assert payload["watchlist"][0]["id"] == "instrument-1"


def test_author_watchlist_remove_returns_updated_list(monkeypatch) -> None:
    author_user = _make_author_user()
    instrument = _make_instrument()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.remove_author_watchlist_instrument",
        lambda _repository, _author, _instrument_id: _async_return(None),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.list_author_watchlist",
        lambda _repository, _author: _async_return([]),
    )

    with _build_client(author_user) as client:
        response = client.post(f"/author/watchlist/items/{instrument.id}/remove")

        assert response.status_code == 200
        payload = response.json()
        assert payload["removed_id"] == instrument.id
        assert payload["watchlist"] == []


def test_author_recommendation_create_page_redirects_to_modal_flow(monkeypatch) -> None:
    author_user = _make_author_user()

    with _build_client(author_user) as client:
        response = client.get("/author/recommendations/new", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/author/recommendations?modal=new"


def test_author_recommendation_embedded_create_page_renders(monkeypatch) -> None:
    author_user = _make_author_user()
    strategy = _make_strategy()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _session, _author: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _session: _async_return([_make_instrument()]))

    with _build_client(author_user) as client:
        response = client.get("/author/recommendations/new?embedded=1&next=/author/recommendations")

        assert response.status_code == 200
        assert "Новая рекомендация" in response.text
        assert "Momentum RU" in response.text
        assert "Основное" in response.text
        assert "Бумаги" in response.text
        assert "Вложения" in response.text
        assert "Действия" in response.text
        assert "+ Добавить бумагу" in response.text
        assert "Политика модерации" in response.text
        assert "Что уже поддержано" not in response.text
        assert 'class="embedded-shell"' in response.text
        assert 'class="staff-shell"' not in response.text
        assert 'action="/author/recommendations"' in response.text
        assert "staff-rail" not in response.text


def test_author_recommendation_detail_prefills_editor(monkeypatch) -> None:
    author_user = _make_author_user()
    strategy = _make_strategy()
    instrument = _make_instrument()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _session, _author: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _session: _async_return([instrument]))

    with _build_client(author_user) as client:
        response = client.get(
            "/author/recommendations/new"
            "?embedded=1"
            "&next=/author/recommendations"
            "&strategy_id=strategy-1"
            "&title=%D0%9F%D0%BE%D0%BA%D1%83%D0%BF%D0%BA%D0%B0%20SBER"
            "&leg_1_instrument_id=instrument-1"
            "&leg_1_side=buy"
            "&leg_1_entry_from=101.5"
            "&leg_1_take_profit_1=106.2"
            "&leg_1_stop_loss=99.9",
        )

        assert response.status_code == 200
        assert 'name="title" value="Покупка SBER"' in response.text
        assert 'value="strategy-1" selected' in response.text
        assert 'value="instrument-1" selected' in response.text
        assert 'name="leg_1_entry_from" value="101.5"' in response.text
        assert 'name="leg_1_take_profit_1" value="106.2"' in response.text
        assert 'name="leg_1_stop_loss" value="99.9"' in response.text
        assert 'option value="buy" selected' in response.text


def test_author_recommendation_create_redirects_to_edit(monkeypatch) -> None:
    author_user = _make_author_user()
    strategy = _make_strategy()
    recommendation = _make_recommendation()
    instrument = _make_instrument()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _session, _author: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _session: _async_return([instrument]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.normalize_attachment_uploads", lambda _files: _async_return([]))
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.create_author_recommendation",
        lambda _session, _author, _data, uploaded_by_user_id=None: _async_return(recommendation),
    )

    with _build_client(author_user) as client:
        response = client.post(
            "/author/recommendations",
            data={
                "strategy_id": "strategy-1",
                "kind": "new_idea",
                "status": "draft",
                "next_path": "/author/recommendations",
                "title": "Покупка SBER",
                "summary": "Кратко",
                "thesis": "Тезис",
                "market_context": "Контекст",
                "leg_7_instrument_id": "instrument-1",
                "leg_7_side": "buy",
                "leg_7_entry_from": "101.5",
                "leg_7_stop_loss": "99.9",
                "leg_7_take_profit_1": "106.2",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/author/recommendations"


def test_author_recommendation_create_publish_now_delivers_notifications(monkeypatch) -> None:
    author_user = _make_author_user()
    strategy = _make_strategy()
    recommendation = _make_recommendation()
    recommendation.status = RecommendationStatus.PUBLISHED
    instrument = _make_instrument()
    delivered: dict[str, object] = {}

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _session, _author: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _session: _async_return([instrument]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.normalize_attachment_uploads", lambda _files: _async_return([]))
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.create_author_recommendation",
        lambda _session, _author, _data, uploaded_by_user_id=None: _async_return(recommendation),
    )

    async def fake_deliver(*, repository, author, recommendation_id, trigger, was_published=False):
        delivered["author_id"] = author.id
        delivered["recommendation_id"] = recommendation_id
        delivered["trigger"] = trigger
        delivered["was_published"] = was_published

    monkeypatch.setattr("pitchcopytrade.api.routes.author._deliver_author_publish_notifications", fake_deliver)

    with _build_client(author_user) as client:
        response = client.post(
            "/author/recommendations",
            data={
                "strategy_id": "strategy-1",
                "kind": "new_idea",
                "status": "draft",
                "workflow_action": "publish_now",
                "title": "Покупка SBER",
                "summary": "Кратко",
                "thesis": "Тезис",
                "market_context": "Контекст",
                "leg_7_instrument_id": "instrument-1",
                "leg_7_side": "buy",
                "leg_7_entry_from": "101.5",
                "leg_7_stop_loss": "99.9",
                "leg_7_take_profit_1": "106.2",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/author/recommendations/rec-1/edit"
        assert delivered == {
            "author_id": "author-1",
            "recommendation_id": "rec-1",
            "trigger": "author_publish_create",
            "was_published": False,
        }


def test_author_recommendation_inline_create_allows_minimal_fields(monkeypatch) -> None:
    author_user = _make_author_user()
    strategy = _make_strategy()
    recommendation = _make_recommendation()
    instrument = _make_instrument()
    captured = {}

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _session, _author: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _session: _async_return([instrument]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.normalize_attachment_uploads", lambda _files: _async_return([]))

    async def _create(_session, _author, data, uploaded_by_user_id=None):
        captured["kind"] = data.kind.value
        captured["entry_from"] = data.legs[0].entry_from
        captured["instrument_id"] = data.legs[0].instrument_id
        return recommendation

    monkeypatch.setattr("pitchcopytrade.api.routes.author.create_author_recommendation", _create)

    with _build_client(author_user) as client:
        response = client.post(
            "/author/recommendations",
            data={
                "inline_mode": "1",
                "strategy_id": "strategy-1",
                "kind": "new_idea",
                "status": "draft",
                "next_path": "/author/recommendations",
                "title": "",
                "leg_1_instrument_id": "instrument-1",
                "leg_1_side": "buy",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/author/recommendations"
        assert captured["kind"] == "new_idea"
        assert captured["entry_from"] is None
        assert captured["instrument_id"] == "instrument-1"


def test_author_recommendation_inline_create_requires_strategy_in_list(monkeypatch) -> None:
    author_user = _make_author_user()
    recommendation = _make_recommendation()
    instrument = _make_instrument()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.list_author_recommendations",
        lambda _session, _author: _async_return([recommendation]),
    )
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _session, _author: _async_return([_make_strategy()]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _session: _async_return([instrument]))

    with _build_client(author_user) as client:
        response = client.post(
            "/author/recommendations",
            data={
                "inline_mode": "1",
                "kind": "new_idea",
                "status": "draft",
                "next_path": "/author/recommendations",
                "title": "",
                "leg_1_instrument_id": "instrument-1",
                "leg_1_side": "buy",
            },
            follow_redirects=False,
        )

        assert response.status_code == 422
        assert "Рекомендации автора" in response.text
        assert "Редактор рекомендации" not in response.text
        assert "Выберите стратегию автора" in response.text
        assert 'name="kind" value="new_idea"' in response.text


def test_author_recommendation_inline_create_price_error_stays_in_list(monkeypatch) -> None:
    author_user = _make_author_user()
    strategy = _make_strategy()
    recommendation = _make_recommendation()
    instrument = _make_instrument()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.list_author_recommendations",
        lambda _session, _author: _async_return([recommendation]),
    )
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _session, _author: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _session: _async_return([instrument]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.normalize_attachment_uploads", lambda _files: _async_return([]))

    with _build_client(author_user) as client:
        response = client.post(
            "/author/recommendations",
            data={
                "inline_mode": "1",
                "strategy_id": "strategy-1",
                "kind": "new_idea",
                "status": "draft",
                "next_path": "/author/recommendations",
                "title": "",
                "instrument_query": "SBER",
                "leg_1_instrument_id": "instrument-1",
                "leg_1_side": "buy",
                "leg_1_entry_from": "105",
                "leg_1_entry_to": "100",
            },
            follow_redirects=False,
        )

        assert response.status_code == 422
        assert "Рекомендации автора" in response.text
        assert "Редактор рекомендации" not in response.text
        assert "Leg 1:" not in response.text
        assert "Цена входа «до» должна быть не ниже цены «от»." in response.text
        assert 'name="leg_1_entry_from" value="105"' in response.text
        assert 'name="leg_1_entry_to" value="100"' in response.text
        assert "Значение не может быть меньше цены «от»" in response.text


def test_author_recommendation_create_validation_error(monkeypatch) -> None:
    author_user = _make_author_user()
    strategy = _make_strategy()
    instrument = _make_instrument()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _session, _author: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _session: _async_return([instrument]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.normalize_attachment_uploads", lambda _files: _async_return([]))

    with _build_client(author_user) as client:
        response = client.post(
            "/author/recommendations",
            data={
                "strategy_id": "unknown",
                "kind": "new_idea",
                "status": "draft",
                "title": "Покупка SBER",
                "summary": "Кратко",
                "thesis": "Тезис",
                "market_context": "Контекст",
            },
        )

        assert response.status_code == 422
        assert "Выберите стратегию автора" in response.text


def test_author_recommendation_create_requires_at_least_one_leg(monkeypatch) -> None:
    author_user = _make_author_user()
    strategy = _make_strategy()
    instrument = _make_instrument()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _session, _author: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _session: _async_return([instrument]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.normalize_attachment_uploads", lambda _files: _async_return([]))

    with _build_client(author_user) as client:
        response = client.post(
            "/author/recommendations",
            data={
                "strategy_id": "strategy-1",
                "kind": "new_idea",
                "status": "draft",
                "title": "Покупка SBER",
                "summary": "Кратко",
                "thesis": "Тезис",
                "market_context": "Контекст",
            },
        )

        assert response.status_code == 422
        assert "Добавьте минимум одну бумагу" in response.text


def test_author_recommendation_edit_page_renders(monkeypatch) -> None:
    author_user = _make_author_user()
    strategy = _make_strategy()
    recommendation = _make_recommendation()
    instrument = _make_instrument()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_recommendation", lambda _session, _author, _id: _async_return(recommendation))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _session, _author: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _session: _async_return([instrument]))

    with _build_client(author_user) as client:
        response = client.get("/author/recommendations/rec-1/edit")

        assert response.status_code == 200
        assert "Редактирование рекомендации" in response.text
        assert "Покупка SBER" in response.text
        assert 'action="/author/recommendations/rec-1"' in response.text


def test_author_recommendation_create_marks_first_leg_instrument_error(monkeypatch) -> None:
    author_user = _make_author_user()
    strategy = _make_strategy()
    instrument = _make_instrument()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _session, _author: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _session: _async_return([instrument]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.normalize_attachment_uploads", lambda _files: _async_return([]))

    with _build_client(author_user) as client:
        response = client.post(
            "/author/recommendations",
            data={
                "strategy_id": "strategy-1",
                "kind": "new_idea",
                "status": "draft",
                "title": "Покупка SBER",
                "leg_7_side": "buy",
            },
        )

        assert response.status_code == 422
        assert "Leg 1:" not in response.text
        assert "Выберите инструмент для первой бумаги." in response.text
        assert "Выберите инструмент из списка" in response.text
        assert 'name="leg_7_instrument_id"' in response.text
        assert 'class="is-invalid"' in response.text


def test_author_recommendation_preview_renders_subscriber_view(monkeypatch) -> None:
    author_user = _make_author_user()
    recommendation = _make_recommendation()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_recommendation", lambda _session, _author, _id: _async_return(recommendation))

    with _build_client(author_user) as client:
        response = client.get("/author/recommendations/rec-1/preview")

        assert response.status_code == 200
        assert "предпросмотр автора" in response.text
        assert "Покупка SBER" in response.text


def test_author_recommendation_edit_submit_redirects(monkeypatch) -> None:
    author_user = _make_author_user()
    strategy = _make_strategy()
    recommendation = _make_recommendation()
    instrument = _make_instrument()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_recommendation", lambda _session, _author, _id: _async_return(recommendation))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _session, _author: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _session: _async_return([instrument]))
    recommendation.attachments = [
        RecommendationAttachment(
            id="att-1",
            recommendation_id="rec-1",
            object_key="recommendations/rec-1/file.pdf",
            original_filename="idea.pdf",
            content_type="application/pdf",
            size_bytes=123,
        )
    ]
    called = {}
    delivered: dict[str, object] = {}

    monkeypatch.setattr("pitchcopytrade.api.routes.author.normalize_attachment_uploads", lambda _files: _async_return([]))
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.remove_recommendation_attachments",
        lambda _session, _recommendation, attachment_ids: _async_return(called.setdefault("attachment_ids", attachment_ids)),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.update_author_recommendation",
        lambda _session, _recommendation, _data, uploaded_by_user_id=None: _async_return(
            called.setdefault("status", _data.status.value) or recommendation
        ),
    )

    async def fake_deliver(*, repository, author, recommendation_id, trigger, was_published=False):
        delivered["author_id"] = author.id
        delivered["recommendation_id"] = recommendation_id
        delivered["trigger"] = trigger
        delivered["was_published"] = was_published

    monkeypatch.setattr("pitchcopytrade.api.routes.author._deliver_author_publish_notifications", fake_deliver)

    with _build_client(author_user) as client:
        response = client.post(
            "/author/recommendations/rec-1",
            data={
                "strategy_id": "strategy-1",
                "kind": "update",
                "status": "review",
                "title": "Покупка SBER",
                "summary": "Кратко",
                "thesis": "Тезис",
                "market_context": "Контекст",
                "scheduled_for": datetime(2026, 3, 12, 12, 30).strftime("%Y-%m-%dT%H:%M"),
                "workflow_action": "publish_now",
                "remove_attachment_ids": "att-1",
                "leg_0_instrument_id": "instrument-1",
                "leg_0_side": "buy",
                "leg_0_entry_from": "101.5",
                "leg_0_stop_loss": "99.9",
                "leg_0_take_profit_1": "106.2",
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/author/recommendations/rec-1/edit"
        assert called["status"] == "published"
        assert called["attachment_ids"] == ["att-1"]
        assert delivered == {
            "author_id": "author-1",
            "recommendation_id": "rec-1",
            "trigger": "author_publish_update",
            "was_published": False,
        }


def test_author_recommendation_create_requires_datetime_for_scheduled(monkeypatch) -> None:
    author_user = _make_author_user()
    strategy = _make_strategy()
    instrument = _make_instrument()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _session, _author: _async_return([strategy]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", lambda _session: _async_return([instrument]))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.normalize_attachment_uploads", lambda _files: _async_return([]))

    with _build_client(author_user) as client:
        response = client.post(
            "/author/recommendations",
            data={
                "strategy_id": "strategy-1",
                "kind": "new_idea",
                "status": "scheduled",
                "title": "Покупка SBER",
            },
        )

        assert response.status_code == 422
        assert "planned datetime" not in response.text
        assert "Укажите дату и время для запланированной публикации." in response.text


def _author_return(author):
    return lambda _session, _user: _async_return(author)


async def _async_return(value):
    return value
