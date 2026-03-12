from __future__ import annotations

from fastapi.testclient import TestClient

from pitchcopytrade.api.deps.repositories import get_auth_repository
from pitchcopytrade.api.main import create_app
from pitchcopytrade.auth.passwords import hash_password
from pitchcopytrade.auth.session import (
    build_session_cookie_value,
    build_telegram_login_link_token,
    get_telegram_fallback_cookie_name,
)
from pitchcopytrade.db.models.accounts import Role, User
from pitchcopytrade.db.models.enums import RoleSlug


class FakeAuthRepository:
    def __init__(self) -> None:
        self.users_by_identity: dict[str, User] = {}
        self.users_by_id: dict[str, User] = {}

    async def get_user_by_identity(self, identity: str) -> User | None:
        return self.users_by_identity.get(identity)

    async def get_user_by_id(self, user_id: str) -> User | None:
        return self.users_by_id.get(user_id)


def _make_user() -> User:
    user = User(
        id="user-1",
        username="alex",
        email="alex@example.com",
        full_name="Alex",
        password_hash=hash_password("test-pass"),
        timezone="Europe/Moscow",
    )
    user.roles = [Role(slug=RoleSlug.AUTHOR, title="Author")]
    return user


def _make_admin_user() -> User:
    user = _make_user()
    user.roles = [Role(slug=RoleSlug.ADMIN, title="Admin")]
    return user


def _make_moderator_user() -> User:
    user = _make_user()
    user.roles = [Role(slug=RoleSlug.MODERATOR, title="Moderator")]
    return user


def _build_client(repository: FakeAuthRepository) -> TestClient:
    app = create_app()

    async def override_auth_repository():
        return repository

    app.dependency_overrides[get_auth_repository] = override_auth_repository
    return TestClient(app)


def test_login_page_renders() -> None:
    repository = FakeAuthRepository()
    with _build_client(repository) as client:
        response = client.get("/login")

        assert response.status_code == 200
        assert "Войти" in response.text


def test_login_submit_sets_session_cookie() -> None:
    repository = FakeAuthRepository()
    user = _make_user()
    repository.users_by_identity[user.username] = user
    repository.users_by_identity[user.email] = user

    with _build_client(repository) as client:
        response = client.post(
            "/login",
            data={"identity": "alex", "password": "test-pass"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/author/dashboard"
        assert "pitchcopytrade_session=" in response.headers["set-cookie"]


def test_login_page_redirects_authenticated_admin_to_dashboard() -> None:
    repository = FakeAuthRepository()
    user = _make_admin_user()
    repository.users_by_id[user.id] = user

    with _build_client(repository) as client:
        client.cookies.set("pitchcopytrade_session", build_session_cookie_value(user))
        response = client.get("/login", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/dashboard"


def test_login_submit_rejects_invalid_credentials() -> None:
    repository = FakeAuthRepository()
    user = _make_user()
    repository.users_by_identity[user.username] = user

    with _build_client(repository) as client:
        response = client.post("/login", data={"identity": "alex", "password": "wrong-pass"})

        assert response.status_code == 401
        assert "Неверный логин или пароль" in response.text


def test_app_requires_session_cookie() -> None:
    repository = FakeAuthRepository()
    with _build_client(repository) as client:
        response = client.get("/app", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/login"


def test_app_home_renders_for_valid_session() -> None:
    repository = FakeAuthRepository()
    user = _make_user()
    repository.users_by_id[user.id] = user

    with _build_client(repository) as client:
        client.cookies.set("pitchcopytrade_session", build_session_cookie_value(user))
        response = client.get("/app", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/author/dashboard"


def test_app_redirects_admin_to_dashboard() -> None:
    repository = FakeAuthRepository()
    user = _make_admin_user()
    repository.users_by_id[user.id] = user

    with _build_client(repository) as client:
        client.cookies.set("pitchcopytrade_session", build_session_cookie_value(user))
        response = client.get("/app", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/dashboard"


def test_login_page_redirects_moderator_to_queue() -> None:
    repository = FakeAuthRepository()
    user = _make_moderator_user()
    repository.users_by_id[user.id] = user

    with _build_client(repository) as client:
        client.cookies.set("pitchcopytrade_session", build_session_cookie_value(user))
        response = client.get("/login", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/moderation/queue"


def test_tg_auth_sets_session_cookie_and_redirects_to_feed() -> None:
    repository = FakeAuthRepository()
    user = _make_user()
    repository.users_by_id[user.id] = user

    with _build_client(repository) as client:
        response = client.get(
            "/tg-auth",
            params={"token": build_telegram_login_link_token(user)},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/app/feed"
        assert f"{get_telegram_fallback_cookie_name()}=" in response.headers["set-cookie"]


def test_tg_auth_respects_safe_next_redirect() -> None:
    repository = FakeAuthRepository()
    user = _make_user()
    repository.users_by_id[user.id] = user

    with _build_client(repository) as client:
        response = client.get(
            "/tg-auth",
            params={"token": build_telegram_login_link_token(user), "next": "/catalog?surface=miniapp"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/catalog?surface=miniapp"


def test_workspace_session_does_not_open_subscriber_feed() -> None:
    repository = FakeAuthRepository()
    user = _make_user()
    repository.users_by_id[user.id] = user

    with _build_client(repository) as client:
        client.cookies.set("pitchcopytrade_session", build_session_cookie_value(user))
        response = client.get("/app/feed", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"].startswith("/verify/telegram?next=/app/feed")


def test_verify_telegram_page_renders() -> None:
    repository = FakeAuthRepository()

    with _build_client(repository) as client:
        response = client.get("/verify/telegram?next=/app/feed")

        assert response.status_code == 200
        assert "Подтвердите доступ через Telegram" in response.text
        assert "/web" in response.text
        assert "start=web" in response.text
