from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from pitchcopytrade.api.deps.auth import require_moderator
from pitchcopytrade.api.main import create_app
from pitchcopytrade.db.models.accounts import AuthorProfile, Role, User
from pitchcopytrade.db.models.audit import AuditEvent
from pitchcopytrade.db.models.catalog import Strategy
from pitchcopytrade.db.models.content import Recommendation
from pitchcopytrade.db.models.enums import RecommendationKind, RecommendationStatus, RiskLevel, RoleSlug, StrategyStatus
from pitchcopytrade.db.session import get_optional_db_session
from pitchcopytrade.repositories.file_store import FileDataStore
from pitchcopytrade.services.moderation import approve_recommendation, build_moderation_detail_metrics


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


def _make_recommendation() -> Recommendation:
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
    recommendation = Recommendation(
        id="rec-1",
        strategy_id="strategy-1",
        author_id="author-1",
        kind=RecommendationKind.NEW_IDEA,
        status=RecommendationStatus.REVIEW,
        title="Покупка SBER",
        summary="Сильный спрос",
        requires_moderation=True,
        scheduled_for=datetime(2026, 3, 12, tzinfo=timezone.utc),
    )
    recommendation.strategy = strategy
    recommendation.author = author
    recommendation.legs = []
    recommendation.attachments = []
    return recommendation


def _build_client(user: User) -> TestClient:
    app = create_app()

    async def override_db_session():
        yield FakeAsyncSession()

    async def override_moderator():
        return user

    app.dependency_overrides[get_optional_db_session] = override_db_session
    app.dependency_overrides[require_moderator] = override_moderator
    return TestClient(app)


def test_moderation_queue_renders(monkeypatch) -> None:
    user = _make_moderator_user()
    recommendation = _make_recommendation()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.moderation.list_moderation_recommendations",
        lambda _session: _async_return([recommendation]),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.moderation.get_moderation_queue_stats",
        lambda _session: _async_return(SimpleNamespace(review_count=1, scheduled_count=0, published_count=0)),
    )

    with _build_client(user) as client:
        response = client.get("/moderation/queue")

        assert response.status_code == 200
        assert "Очередь модерации" in response.text
        assert "Покупка SBER" in response.text


def test_moderation_queue_accepts_filters(monkeypatch) -> None:
    user = _make_moderator_user()
    recommendation = _make_recommendation()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.moderation.list_moderation_recommendations",
        lambda _session, **kwargs: _async_return([recommendation]),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.moderation.get_moderation_queue_stats",
        lambda _session: _async_return(SimpleNamespace(review_count=1, scheduled_count=0, published_count=0)),
    )

    with _build_client(user) as client:
        response = client.get("/moderation/queue?q=sber&status_value=review")

        assert response.status_code == 200
        assert "Применить" in response.text
        assert "Покупка SBER" in response.text


def test_moderation_detail_renders(monkeypatch) -> None:
    user = _make_moderator_user()
    recommendation = _make_recommendation()
    history = [
        AuditEvent(
            id="audit-1",
            entity_type="recommendation",
            entity_id="rec-1",
            action="moderation.approve",
            payload={"status": "published"},
        )
    ]
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.moderation.get_moderation_recommendation",
        lambda _session, _id: _async_return(recommendation),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.moderation.list_recommendation_audit_events",
        lambda _session, _id: _async_return(history),
    )

    with _build_client(user) as client:
        response = client.get("/moderation/recommendations/rec-1")

        assert response.status_code == 200
        assert "Одобрить" in response.text
        assert "Momentum RU" in response.text
        assert "moderation.approve" in response.text
        assert "SLA:" in response.text


def test_moderation_approve_redirects(monkeypatch) -> None:
    user = _make_moderator_user()
    recommendation = _make_recommendation()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.moderation.get_moderation_recommendation",
        lambda _session, _id: _async_return(recommendation),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.moderation.approve_recommendation",
        lambda _session, _recommendation, _user, _comment: _async_return(recommendation),
    )

    with _build_client(user) as client:
        response = client.post("/moderation/recommendations/rec-1/approve", data={"comment": "OK"}, follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/moderation/recommendations/rec-1"


def test_moderation_rework_redirects(monkeypatch) -> None:
    user = _make_moderator_user()
    recommendation = _make_recommendation()
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.moderation.get_moderation_recommendation",
        lambda _session, _id: _async_return(recommendation),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.moderation.send_recommendation_to_rework",
        lambda _session, _recommendation, _user, _comment: _async_return(recommendation),
    )

    with _build_client(user) as client:
        response = client.post("/moderation/recommendations/rec-1/rework", data={"comment": "Нужна доработка"}, follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/moderation/recommendations/rec-1"


async def test_file_mode_approve_recommendation_updates_seed_runtime(tmp_path) -> None:
    now = datetime(2026, 3, 12, tzinfo=timezone.utc).isoformat()
    store = FileDataStore(root_dir=tmp_path, seed_dir=tmp_path)
    store.save_many(
        {
            "roles": [{"id": "role-mod", "slug": "moderator", "title": "Moderator", "created_at": now, "updated_at": now}],
            "users": [
                {
                    "id": "moderator-1",
                    "email": "mod@example.com",
                    "telegram_user_id": None,
                    "username": "mod1",
                    "full_name": "Moderator",
                    "password_hash": None,
                    "status": "active",
                    "timezone": "Europe/Moscow",
                    "lead_source_id": None,
                    "role_ids": ["role-mod"],
                    "created_at": now,
                    "updated_at": now,
                },
                {
                    "id": "author-user-1",
                    "email": "author@example.com",
                    "telegram_user_id": None,
                    "username": "author1",
                    "full_name": "Author",
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
                    "user_id": "author-user-1",
                    "display_name": "Alpha Desk",
                    "slug": "alpha-desk",
                    "bio": None,
                    "requires_moderation": True,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
            "lead_sources": [],
            "instruments": [],
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
                    "min_capital_rub": 100000,
                    "is_public": True,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
            "bundles": [],
            "bundle_members": [],
            "products": [],
            "legal_documents": [],
            "payments": [],
            "subscriptions": [],
            "user_consents": [],
            "audit_events": [],
            "recommendations": [
                {
                    "id": "rec-1",
                    "strategy_id": "strategy-1",
                    "author_id": "author-1",
                    "moderated_by_user_id": None,
                    "kind": "new_idea",
                    "status": "review",
                    "title": "Покупка SBER",
                    "summary": "Сильный спрос",
                    "thesis": None,
                    "market_context": None,
                    "requires_moderation": True,
                    "scheduled_for": None,
                    "published_at": None,
                    "closed_at": None,
                    "cancelled_at": None,
                    "moderation_comment": None,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
            "recommendation_legs": [],
            "recommendation_attachments": [],
        }
    )

    recommendation = _make_recommendation()
    moderator = _make_moderator_user()
    updated = await approve_recommendation(None, recommendation, moderator, "OK", store=store)

    assert updated.status == RecommendationStatus.PUBLISHED
    assert updated.moderation_comment == "OK"


def test_build_moderation_detail_metrics_detects_overdue() -> None:
    recommendation = _make_recommendation()
    recommendation.created_at = datetime(2026, 3, 10, tzinfo=timezone.utc)

    metrics = build_moderation_detail_metrics(
        recommendation,
        [],
        now=datetime(2026, 3, 12, tzinfo=timezone.utc),
    )

    assert metrics.sla_state == "overdue"
    assert metrics.resolution_hours is None


async def _async_return(value):
    return value
