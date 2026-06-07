from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from pitchcopytrade.api.deps.auth import require_moderator
from pitchcopytrade.api.deps.repositories import get_optional_db_session
from pitchcopytrade.api.main import create_app
from pitchcopytrade.db.models.accounts import AuthorProfile, Role, User
from pitchcopytrade.db.models.catalog import Strategy
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.enums import MessageKind, MessageStatus, RiskLevel, RoleSlug, StrategyStatus


class FakeAsyncSession:
    async def execute(self, query):
        raise AssertionError("This suite expects monkeypatched service calls")


def _make_moderator_user() -> User:
    user = User(
        id="moderator-1",
        username="mod1",
        email="mod@example.com",
        full_name="Moderator",
        timezone="Europe/Moscow",
    )
    user.roles = [Role(slug=RoleSlug.MODERATOR, title="Moderator")]
    return user


def _make_message() -> Message:
    author_user = User(id="author-user-1", full_name="Alpha Desk")
    author = AuthorProfile(
        id="author-1",
        user_id="author-user-1",
        display_name="Alpha Desk",
        slug="alpha-desk",
        is_active=True,
    )
    author.user = author_user
    strategy = Strategy(
        id="strategy-1",
        author_id="author-1",
        slug="momentum-ru",
        title="Momentum RU",
        short_description="Системная стратегия",
        full_description="Полное описание",
        risk_level=RiskLevel.MEDIUM,
        status=StrategyStatus.PUBLISHED,
        min_capital_rub=150000,
        is_public=True,
    )
    strategy.author = author
    message = Message(
        id="msg-1",
        strategy_id="strategy-1",
        author_id="author-1",
        kind=MessageKind.IDEA,
        status=MessageStatus.REVIEW,
        title="Покупка SBER",
        moderation="required",
        text={"body": "<p>Сильный спрос</p>", "plain": "Сильный спрос"},
        documents=[],
        deals=[],
        created=datetime(2026, 3, 12, tzinfo=timezone.utc),
        updated=datetime(2026, 3, 12, tzinfo=timezone.utc),
    )
    message.strategy = strategy
    message.author = author
    return message


def _build_client(user: User) -> TestClient:
    app = create_app()

    async def override_db_session():
        yield FakeAsyncSession()

    async def override_moderator():
        return user

    app.dependency_overrides[get_optional_db_session] = override_db_session
    app.dependency_overrides[require_moderator] = override_moderator
    return TestClient(app)


def test_moderation_queue_renders_message_rows(monkeypatch) -> None:
    user = _make_moderator_user()
    message = _make_message()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.moderation.list_moderation_recommendations",
        lambda _session: _async_return([message]),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.moderation.get_moderation_queue_stats",
        lambda _session: _async_return(type("Stats", (), {"review_count": 1, "scheduled_count": 0, "published_count": 0})()),
    )

    with _build_client(user) as client:
        response = client.get("/moderation/queue")

        assert response.status_code == 200
        assert "Очередь модерации" in response.text
        assert "Покупка SBER" in response.text
        assert "Формат" in response.text


def test_moderation_detail_renders_message_contract(monkeypatch) -> None:
    user = _make_moderator_user()
    message = _make_message()
    history = [type("Audit", (), {"id": "audit-1"})()]
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.moderation.get_moderation_message",
        lambda _session, _id: _async_return(message),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.moderation.list_message_audit_events",
        lambda _session, _id: _async_return(history),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.moderation.build_moderation_detail_metrics",
        lambda _message, _history: type("Metrics", (), {"sla_state": "on_time", "resolution_hours": 1})(),
    )

    with _build_client(user) as client:
        response = client.get("/moderation/messages/msg-1")

        assert response.status_code == 200
        assert "message thread" in response.text
        assert "Что увидит подписчик" in response.text
        assert "Сильный спрос" in response.text
        assert "documents" not in response.text or "Документов" in response.text


def test_moderation_approve_redirects(monkeypatch) -> None:
    user = _make_moderator_user()
    message = _make_message()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.moderation.get_moderation_message",
        lambda _session, _id: _async_return(message),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.moderation.approve_message",
        lambda _session, _message, _user, _comment: _async_return(message),
    )

    with _build_client(user) as client:
        response = client.post("/moderation/messages/msg-1/approve", data={"comment": "OK"}, follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/moderation/messages/msg-1"


def test_moderation_rework_redirects(monkeypatch) -> None:
    user = _make_moderator_user()
    message = _make_message()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.moderation.get_moderation_message",
        lambda _session, _id: _async_return(message),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.moderation.send_message_to_rework",
        lambda _session, _message, _user, _comment: _async_return(message),
    )

    with _build_client(user) as client:
        response = client.post("/moderation/messages/msg-1/rework", data={"comment": "Нужна доработка"}, follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/moderation/messages/msg-1"


async def _async_return(value):
    return value
