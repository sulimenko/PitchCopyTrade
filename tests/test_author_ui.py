from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from pitchcopytrade.api.deps.auth import require_author
from pitchcopytrade.api.main import create_app
from pitchcopytrade.db.models.accounts import AuthorProfile, Role, User
from pitchcopytrade.db.models.catalog import Strategy
from pitchcopytrade.db.models.content import Recommendation
from pitchcopytrade.db.models.enums import RecommendationKind, RecommendationStatus, RiskLevel, RoleSlug, StrategyStatus
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

    with _build_client(author_user) as client:
        response = client.get("/author/dashboard")

        assert response.status_code == 200
        assert "Author One" in response.text
        assert "Momentum RU" in response.text
        assert "Покупка SBER" in response.text


def test_author_recommendation_list_renders(monkeypatch) -> None:
    author_user = _make_author_user()
    recommendation = _make_recommendation()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.list_author_recommendations",
        lambda _session, _author: _async_return([recommendation]),
    )

    with _build_client(author_user) as client:
        response = client.get("/author/recommendations")

        assert response.status_code == 200
        assert "Рекомендации автора" in response.text
        assert "Покупка SBER" in response.text


def test_author_recommendation_create_page_renders(monkeypatch) -> None:
    author_user = _make_author_user()
    strategy = _make_strategy()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _session, _author: _async_return([strategy]))

    with _build_client(author_user) as client:
        response = client.get("/author/recommendations/new")

        assert response.status_code == 200
        assert "Новая рекомендация" in response.text
        assert "Momentum RU" in response.text


def test_author_recommendation_create_redirects_to_edit(monkeypatch) -> None:
    author_user = _make_author_user()
    strategy = _make_strategy()
    recommendation = _make_recommendation()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _session, _author: _async_return([strategy]))
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.create_author_recommendation",
        lambda _session, _author, _data: _async_return(recommendation),
    )

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
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/author/recommendations/rec-1/edit"


def test_author_recommendation_create_validation_error(monkeypatch) -> None:
    author_user = _make_author_user()
    strategy = _make_strategy()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _session, _author: _async_return([strategy]))

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


def test_author_recommendation_edit_page_renders(monkeypatch) -> None:
    author_user = _make_author_user()
    strategy = _make_strategy()
    recommendation = _make_recommendation()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_recommendation", lambda _session, _author, _id: _async_return(recommendation))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _session, _author: _async_return([strategy]))

    with _build_client(author_user) as client:
        response = client.get("/author/recommendations/rec-1/edit")

        assert response.status_code == 200
        assert "Редактирование рекомендации" in response.text
        assert "Покупка SBER" in response.text


def test_author_recommendation_edit_submit_redirects(monkeypatch) -> None:
    author_user = _make_author_user()
    strategy = _make_strategy()
    recommendation = _make_recommendation()

    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_by_user", _author_return(author_user.author_profile))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.get_author_recommendation", lambda _session, _author, _id: _async_return(recommendation))
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", lambda _session, _author: _async_return([strategy]))
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.update_author_recommendation",
        lambda _session, _recommendation, _data: _async_return(recommendation),
    )

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
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/author/recommendations/rec-1/edit"


def _author_return(author):
    return lambda _session, _user: _async_return(author)


async def _async_return(value):
    return value
