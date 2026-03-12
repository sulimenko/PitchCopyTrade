from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi.testclient import TestClient

from pitchcopytrade.api.deps.repositories import get_public_repository
from pitchcopytrade.api.deps.repositories import get_auth_repository
from pitchcopytrade.api.main import create_app
from pitchcopytrade.auth.passwords import hash_password
from pitchcopytrade.auth.session import (
    build_session_cookie_value,
    build_telegram_login_link_token,
    get_telegram_fallback_cookie_name,
)
from pitchcopytrade.core.config import reset_settings_cache
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


class FakePublicRepository:
    def __init__(self) -> None:
        self.user_by_telegram_id: dict[int, User] = {}
        self.added: list[object] = []

    async def list_public_strategies(self):
        return []

    async def get_public_strategy_by_slug(self, slug: str):
        return None

    async def get_public_product(self, product_id: str):
        return None

    async def get_public_product_by_slug(self, slug: str):
        return None

    async def list_active_checkout_documents(self):
        return []

    async def find_user_by_email(self, email: str):
        return None

    async def get_user_by_telegram_id(self, telegram_user_id: int):
        return self.user_by_telegram_id.get(telegram_user_id)

    def add(self, entity: object) -> None:
        self.added.append(entity)
        if isinstance(entity, User) and entity.telegram_user_id is not None:
            self.user_by_telegram_id[entity.telegram_user_id] = entity

    async def commit(self) -> None:
        return None

    async def refresh(self, entity: object) -> None:
        return None


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


def _build_client(repository: FakeAuthRepository, public_repository: FakePublicRepository | None = None) -> TestClient:
    app = create_app()

    async def override_auth_repository():
        return repository

    async def override_public_repository():
        return public_repository or FakePublicRepository()

    app.dependency_overrides[get_auth_repository] = override_auth_repository
    app.dependency_overrides[get_public_repository] = override_public_repository
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
        assert response.headers["location"] == "/app/status"
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
        assert "Mini App автоматически подтвердит" in response.text
        assert "Открыть бота" in response.text


def test_tg_webapp_auth_sets_cookie_and_returns_redirect(monkeypatch) -> None:
    repository = FakeAuthRepository()
    public_repository = FakePublicRepository()
    auth_date = int(datetime.now(timezone.utc).timestamp())
    init_data = _build_webapp_init_data(
        bot_token="test-bot-token",
        auth_date=auth_date,
        user_payload={
            "id": 12345,
            "username": "leaduser",
            "first_name": "Lead",
            "last_name": "User",
        },
    )

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-bot-token")
    reset_settings_cache()
    with _build_client(repository, public_repository) as client:
        response = client.post(
            "/tg-webapp/auth",
            data={"init_data": init_data, "next": "/app/status"},
        )

        assert response.status_code == 200
        assert response.json()["redirect_url"] == "/app/status"
        assert f"{get_telegram_fallback_cookie_name()}=" in response.headers["set-cookie"]
    reset_settings_cache()


def _build_webapp_init_data(*, bot_token: str, auth_date: int, user_payload: dict[str, object]) -> str:
    items = {
        "auth_date": str(auth_date),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps(user_payload, separators=(",", ":"), ensure_ascii=False),
    }
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(items.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    items["hash"] = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    return urlencode(items)
