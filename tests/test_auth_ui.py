from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from pitchcopytrade.api.main import create_app
from pitchcopytrade.auth.passwords import hash_password
from pitchcopytrade.auth.session import (
    build_session_cookie_value,
    build_telegram_login_link_token,
    get_telegram_fallback_cookie_name,
)
from pitchcopytrade.db.models.accounts import Role, User
from pitchcopytrade.db.models.enums import RoleSlug
from pitchcopytrade.db.session import get_db_session


class FakeAsyncSession:
    def __init__(self) -> None:
        self.users_by_identity: dict[str, User] = {}
        self.users_by_id: dict[str, User] = {}

    async def execute(self, query: Any):
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))

        class Result:
            def __init__(self, user: User | None) -> None:
                self._user = user

            def scalar_one_or_none(self) -> User | None:
                return self._user

        for identity, user in self.users_by_identity.items():
            if f"'{identity}'" in compiled:
                return Result(user)

        for user_id, user in self.users_by_id.items():
            if f"'{user_id}'" in compiled:
                return Result(user)

        if "users.id" in compiled and len(self.users_by_id) == 1:
            return Result(next(iter(self.users_by_id.values())))

        return Result(None)


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


def _build_client(session: FakeAsyncSession) -> TestClient:
    app = create_app()

    async def override_db_session():
        yield session

    app.dependency_overrides[get_db_session] = override_db_session
    return TestClient(app)


def test_login_page_renders() -> None:
    session = FakeAsyncSession()
    with _build_client(session) as client:
        response = client.get("/login")

        assert response.status_code == 200
        assert "Войти" in response.text


def test_login_submit_sets_session_cookie() -> None:
    session = FakeAsyncSession()
    user = _make_user()
    session.users_by_identity[user.username] = user
    session.users_by_identity[user.email] = user

    with _build_client(session) as client:
        response = client.post(
            "/login",
            data={"identity": "alex", "password": "test-pass"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/workspace"
        assert "pitchcopytrade_session=" in response.headers["set-cookie"]


def test_login_page_redirects_authenticated_admin_to_dashboard() -> None:
    session = FakeAsyncSession()
    user = _make_admin_user()
    session.users_by_id[user.id] = user

    with _build_client(session) as client:
        client.cookies.set("pitchcopytrade_session", build_session_cookie_value(user))
        response = client.get("/login", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/dashboard"


def test_login_submit_rejects_invalid_credentials() -> None:
    session = FakeAsyncSession()
    user = _make_user()
    session.users_by_identity[user.username] = user

    with _build_client(session) as client:
        response = client.post("/login", data={"identity": "alex", "password": "wrong-pass"})

        assert response.status_code == 401
        assert "Неверный логин или пароль" in response.text


def test_app_requires_session_cookie() -> None:
    session = FakeAsyncSession()
    with _build_client(session) as client:
        response = client.get("/app", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/login"


def test_app_home_renders_for_valid_session() -> None:
    session = FakeAsyncSession()
    user = _make_user()
    session.users_by_id[user.id] = user

    with _build_client(session) as client:
        client.cookies.set("pitchcopytrade_session", build_session_cookie_value(user))
        response = client.get("/app", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/workspace"


def test_app_redirects_admin_to_dashboard() -> None:
    session = FakeAsyncSession()
    user = _make_admin_user()
    session.users_by_id[user.id] = user

    with _build_client(session) as client:
        client.cookies.set("pitchcopytrade_session", build_session_cookie_value(user))
        response = client.get("/app", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/dashboard"


def test_tg_auth_sets_session_cookie_and_redirects_to_feed() -> None:
    session = FakeAsyncSession()
    user = _make_user()
    session.users_by_id[user.id] = user

    with _build_client(session) as client:
        response = client.get(
            "/tg-auth",
            params={"token": build_telegram_login_link_token(user)},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/app/feed"
        assert f"{get_telegram_fallback_cookie_name()}=" in response.headers["set-cookie"]


def test_workspace_session_does_not_open_subscriber_feed() -> None:
    session = FakeAsyncSession()
    user = _make_user()
    session.users_by_id[user.id] = user

    with _build_client(session) as client:
        client.cookies.set("pitchcopytrade_session", build_session_cookie_value(user))
        response = client.get("/app/feed", follow_redirects=False)

        assert response.status_code == 401
