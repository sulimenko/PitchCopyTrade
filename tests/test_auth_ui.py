from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi.testclient import TestClient

from pitchcopytrade.api.deps.repositories import get_public_repository
from pitchcopytrade.api.deps.repositories import get_auth_repository
from pitchcopytrade.api.deps.repositories import get_author_repository
from pitchcopytrade.api.main import create_app
from pitchcopytrade.auth.passwords import hash_password
from pitchcopytrade.auth.staff_mode import resolve_staff_mode
from pitchcopytrade.auth.staff_mode import get_staff_mode_cookie_name
from pitchcopytrade.auth.session import (
    build_staff_invite_token,
    build_session_cookie_value,
    build_telegram_fallback_cookie_value,
    build_telegram_login_link_token,
    get_telegram_fallback_cookie_name,
)
from pitchcopytrade.core.config import get_settings, reset_settings_cache
from pitchcopytrade.db.models.accounts import AuthorProfile, Role, User
from pitchcopytrade.db.models.catalog import Instrument, Strategy
from pitchcopytrade.db.models.enums import InstrumentType, RoleSlug, RiskLevel, StrategyStatus, UserStatus


class FakeAuthRepository:
    def __init__(self) -> None:
        self.users_by_identity: dict[str, User] = {}
        self.users_by_id: dict[str, User] = {}
        self.users_by_telegram_id: dict[int, User] = {}

    async def get_user_by_identity(self, identity: str) -> User | None:
        return self.users_by_identity.get(identity)

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> User | None:
        return self.users_by_telegram_id.get(telegram_user_id)

    async def get_user_by_id(self, user_id: str) -> User | None:
        return self.users_by_id.get(user_id)

    async def commit(self) -> None:
        return None


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


class FakeAuthorRepository:
    def __init__(self, user: User) -> None:
        self.user = user

    async def get_author_by_user_id(self, user_id: str) -> AuthorProfile | None:
        if user_id == self.user.id:
            return self.user.author_profile
        return None


def _make_user() -> User:
    user = User(
        id="user-1",
        username="alex",
        email="alex@example.com",
        full_name="Alex",
        password_hash=hash_password("test-pass"),
        timezone="Europe/Moscow",
        status=UserStatus.ACTIVE,
    )
    user.roles = [Role(slug=RoleSlug.AUTHOR, title="Author")]
    return user


def _make_admin_user() -> User:
    user = _make_user()
    user.roles = [Role(slug=RoleSlug.ADMIN, title="Admin")]
    return user


def _make_dual_role_user() -> User:
    user = _make_user()
    user.roles = [
        Role(slug=RoleSlug.ADMIN, title="Admin"),
        Role(slug=RoleSlug.AUTHOR, title="Author"),
    ]
    user.author_profile = AuthorProfile(id="author-1", user_id=user.id, display_name="Alex", slug="alex")
    return user


def _make_moderator_user() -> User:
    user = _make_user()
    user.roles = [Role(slug=RoleSlug.MODERATOR, title="Moderator")]
    return user


def _build_client(
    repository: FakeAuthRepository,
    public_repository: FakePublicRepository | None = None,
    author_repository: FakeAuthorRepository | None = None,
) -> TestClient:
    app = create_app()

    async def override_auth_repository():
        return repository

    async def override_public_repository():
        return public_repository or FakePublicRepository()

    async def override_author_repository():
        return author_repository

    app.dependency_overrides[get_auth_repository] = override_auth_repository
    app.dependency_overrides[get_public_repository] = override_public_repository
    app.dependency_overrides[get_author_repository] = override_author_repository
    return TestClient(app)


def test_login_page_renders() -> None:
    repository = FakeAuthRepository()
    with _build_client(repository) as client:
        response = client.get("/login")

        assert response.status_code == 200
        assert "PitchCopyTrade" in response.text
        assert "Логин или email" in response.text
        assert "Клиентам входить через Telegram-бота" in response.text
        assert "/setdomain" in response.text
        assert "/auth/telegram/callback" in response.text


def test_login_page_renders_staff_invite_state() -> None:
    repository = FakeAuthRepository()
    with _build_client(repository) as client:
        response = client.get("/login?invite_token=test-token")

        assert response.status_code == 200
        assert "Приглашение сотрудника активно" in response.text
        assert "Один шаг через Telegram" in response.text
        assert "Открыть Telegram" in response.text
        assert "Скопировать приглашение" in response.text
        assert "Запросить новое приглашение" in response.text
        assert "Логин или email" not in response.text


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


def test_telegram_widget_callback_accepts_extra_query_fields() -> None:
    repository = FakeAuthRepository()
    user = _make_author_user_with_telegram_id(telegram_user_id=777001)
    repository.users_by_telegram_id[user.telegram_user_id] = user

    with _build_client(repository) as client:
        auth_date = int(datetime.now(timezone.utc).timestamp())
        params = {
            "id": str(user.telegram_user_id),
            "first_name": "Alex",
            "username": "alex_author",
            "photo_url": "https://t.me/i/userpic/320/demo.jpg",
            "auth_date": str(auth_date),
        }
        data_check = "\n".join(f"{key}={value}" for key, value in sorted(params.items()))
        secret = hashlib.sha256(get_settings().telegram.bot_token.get_secret_value().encode()).digest()
        params["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        response = client.get("/auth/telegram/callback", params=params, follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/author/dashboard"


def test_telegram_widget_callback_rejects_invited_user_without_invite_token() -> None:
    repository = FakeAuthRepository()
    user = _make_author_user_with_telegram_id(telegram_user_id=777001)
    user.status = UserStatus.INVITED
    repository.users_by_telegram_id[user.telegram_user_id] = user

    with _build_client(repository) as client:
        auth_date = int(datetime.now(timezone.utc).timestamp())
        params = {
            "id": str(user.telegram_user_id),
            "first_name": "Alex",
            "username": "alex_author",
            "auth_date": str(auth_date),
        }
        data_check = "\n".join(f"{key}={value}" for key, value in sorted(params.items()))
        secret = hashlib.sha256(get_settings().telegram.bot_token.get_secret_value().encode()).digest()
        params["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()

        response = client.get("/auth/telegram/callback", params=params)

        assert response.status_code == 401
        assert "не найден среди сотрудников" in response.text


def _make_author_user_with_telegram_id(*, telegram_user_id: int) -> User:
    user = _make_user()
    user.telegram_user_id = telegram_user_id
    return user


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


def test_login_submit_rejects_invited_staff_user() -> None:
    repository = FakeAuthRepository()
    user = _make_user()
    user.status = UserStatus.INVITED
    repository.users_by_identity[user.username] = user

    with _build_client(repository) as client:
        response = client.post("/login", data={"identity": "alex", "password": "test-pass"})

        assert response.status_code == 403
        assert "ещё не активирован" in response.text


def test_app_requires_session_cookie() -> None:
    repository = FakeAuthRepository()
    with _build_client(repository) as client:
        response = client.get("/app", follow_redirects=False)

        assert response.status_code == 200
        assert "Открываем каталог стратегий" in response.text


def test_app_redirects_tg_fallback_user_to_catalog() -> None:
    repository = FakeAuthRepository()
    user = _make_user()
    repository.users_by_id[user.id] = user

    with _build_client(repository) as client:
        client.cookies.set(get_telegram_fallback_cookie_name(), build_telegram_fallback_cookie_value(user))
        response = client.get("/app", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/app/catalog"


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


def test_telegram_invite_token_binds_author_account() -> None:
    repository = FakeAuthRepository()
    user = _make_user()
    user.status = UserStatus.INVITED
    repository.users_by_id[user.id] = user

    with _build_client(repository) as client:
        auth_date = int(datetime.now(timezone.utc).timestamp())
        params = {
            "id": "777001",
            "first_name": "Alex",
            "username": "alex_author",
            "auth_date": str(auth_date),
            "invite_token": build_staff_invite_token(user),
        }
        data_check = "\n".join(f"{key}={value}" for key, value in sorted({k: v for k, v in params.items() if k != "invite_token"}.items()))
        secret = hashlib.sha256(get_settings().telegram.bot_token.get_secret_value().encode()).digest()
        params["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()

        response = client.get("/auth/telegram/callback", params=params, follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/author/dashboard"
        assert user.telegram_user_id == 777001


def test_telegram_invite_token_binds_prefilled_author_account() -> None:
    repository = FakeAuthRepository()
    user = _make_author_user_with_telegram_id(telegram_user_id=777001)
    user.status = UserStatus.INVITED
    repository.users_by_id[user.id] = user
    repository.users_by_telegram_id[user.telegram_user_id] = user

    with _build_client(repository) as client:
        auth_date = int(datetime.now(timezone.utc).timestamp())
        params = {
            "id": "777001",
            "first_name": "Alex",
            "username": "alex_author",
            "auth_date": str(auth_date),
            "invite_token": build_staff_invite_token(user),
        }
        data_check = "\n".join(f"{key}={value}" for key, value in sorted({k: v for k, v in params.items() if k != "invite_token"}.items()))
        secret = hashlib.sha256(get_settings().telegram.bot_token.get_secret_value().encode()).digest()
        params["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()

        response = client.get("/auth/telegram/callback", params=params, follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/author/dashboard"
        assert user.status == UserStatus.ACTIVE


def test_telegram_invite_token_binds_admin_account() -> None:
    repository = FakeAuthRepository()
    user = _make_admin_user()
    user.status = UserStatus.INVITED
    repository.users_by_id[user.id] = user

    with _build_client(repository) as client:
        auth_date = int(datetime.now(timezone.utc).timestamp())
        params = {
            "id": "888002",
            "first_name": "Ops",
            "username": "ops_admin",
            "auth_date": str(auth_date),
            "invite_token": build_staff_invite_token(user),
        }
        data_check = "\n".join(f"{key}={value}" for key, value in sorted({k: v for k, v in params.items() if k != "invite_token"}.items()))
        secret = hashlib.sha256(get_settings().telegram.bot_token.get_secret_value().encode()).digest()
        params["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()

        response = client.get("/auth/telegram/callback", params=params, follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/dashboard"
        assert user.telegram_user_id == 888002
        assert user.status == UserStatus.ACTIVE


def test_telegram_invite_token_rejects_stale_token_after_version_bump() -> None:
    repository = FakeAuthRepository()
    user = _make_admin_user()
    user.status = UserStatus.INVITED
    stale_token = build_staff_invite_token(user)
    user.invite_token_version = 2
    repository.users_by_id[user.id] = user

    with _build_client(repository) as client:
        auth_date = int(datetime.now(timezone.utc).timestamp())
        params = {
            "id": "888002",
            "first_name": "Ops",
            "username": "ops_admin",
            "auth_date": str(auth_date),
            "invite_token": stale_token,
        }
        data_check = "\n".join(f"{key}={value}" for key, value in sorted({k: v for k, v in params.items() if k != "invite_token"}.items()))
        secret = hashlib.sha256(get_settings().telegram.bot_token.get_secret_value().encode()).digest()
        params["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()

        response = client.get("/auth/telegram/callback", params=params)

        assert response.status_code == 409
        assert "Приглашение недействительно или устарело." in response.text
        assert user.status == UserStatus.INVITED


def test_telegram_invite_token_rejects_telegram_collision() -> None:
    repository = FakeAuthRepository()
    invited_user = _make_admin_user()
    invited_user.id = "staff-1"
    invited_user.status = UserStatus.INVITED
    repository.users_by_id[invited_user.id] = invited_user

    existing_user = _make_user()
    existing_user.id = "staff-2"
    existing_user.telegram_user_id = 777001
    repository.users_by_telegram_id[existing_user.telegram_user_id] = existing_user

    with _build_client(repository) as client:
        auth_date = int(datetime.now(timezone.utc).timestamp())
        params = {
            "id": "777001",
            "first_name": "Alex",
            "username": "alex_author",
            "auth_date": str(auth_date),
            "invite_token": build_staff_invite_token(invited_user),
        }
        data_check = "\n".join(f"{key}={value}" for key, value in sorted({k: v for k, v in params.items() if k != "invite_token"}.items()))
        secret = hashlib.sha256(get_settings().telegram.bot_token.get_secret_value().encode()).digest()
        params["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()

        response = client.get("/auth/telegram/callback", params=params)

        assert response.status_code == 409
        assert "Этот Telegram-аккаунт уже привязан к другому сотруднику." in response.text
        assert invited_user.status == UserStatus.INVITED


def test_dual_role_login_defaults_to_admin_mode() -> None:
    repository = FakeAuthRepository()
    user = _make_dual_role_user()
    repository.users_by_identity[user.username] = user

    with _build_client(repository) as client:
        response = client.post("/login", data={"identity": "alex", "password": "test-pass"}, follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/dashboard"
        assert "pitchcopytrade_session_staff_mode=admin" in response.headers["set-cookie"]


def test_dual_role_can_switch_to_author_mode() -> None:
    repository = FakeAuthRepository()
    user = _make_dual_role_user()
    repository.users_by_id[user.id] = user

    with _build_client(repository) as client:
        client.cookies.set("pitchcopytrade_session", build_session_cookie_value(user))
        response = client.post("/auth/mode", data={"mode": "author", "next": "/admin/authors"}, follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/author/dashboard"
        assert "pitchcopytrade_session_staff_mode=author" in response.headers["set-cookie"]


def test_dual_role_can_switch_to_author_mode_and_render_dashboard(monkeypatch) -> None:
    repository = FakeAuthRepository()
    user = _make_dual_role_user()
    repository.users_by_id[user.id] = user
    author_repository = FakeAuthorRepository(user)
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
        author_id=user.author_profile.id,
        slug="momentum-ru",
        title="Momentum RU",
        short_description="desc",
        full_description="full",
        risk_level=RiskLevel.MEDIUM,
        status=StrategyStatus.PUBLISHED,
        min_capital_rub=150000,
        is_public=True,
    )
    async def fake_stats(_repository, _author):
        return type("Stats", (), {
            "strategies_total": 1,
            "messages_total": 0,
            "draft_messages": 0,
            "live_messages": 0,
        })()

    async def fake_strategies(_repository, _author):
        return [strategy]

    async def fake_recommendations(_repository, _author):
        return []

    async def fake_watchlist(_repository, _author):
        return [instrument]

    async def fake_instruments(_repository):
        return [instrument]

    monkeypatch.setattr(
        "pitchcopytrade.api.routes.author.get_author_workspace_stats",
        fake_stats,
    )
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_strategies", fake_strategies)
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_recommendations", fake_recommendations)
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_author_watchlist", fake_watchlist)
    monkeypatch.setattr("pitchcopytrade.api.routes.author.list_active_instruments", fake_instruments)

    def fail_on_live_fetch(**_kwargs):
        raise AssertionError("live quote provider should not be called during author dashboard render")

    monkeypatch.setattr("pitchcopytrade.services.instruments.httpx.AsyncClient", fail_on_live_fetch)

    with _build_client(repository, author_repository=author_repository) as client:
        client.cookies.set("pitchcopytrade_session", build_session_cookie_value(user))
        response = client.post("/auth/mode", data={"mode": "author", "next": "/admin/authors"}, follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/author/dashboard"
        client.cookies.set(get_staff_mode_cookie_name(), "author")

        dashboard = client.get("/author/dashboard")
        assert dashboard.status_code == 200
        assert "Авторский кабинет" in dashboard.text or "Последние сообщения" in dashboard.text


def test_dual_role_can_switch_back_to_admin_mode() -> None:
    repository = FakeAuthRepository()
    user = _make_dual_role_user()
    repository.users_by_id[user.id] = user

    with _build_client(repository) as client:
        client.cookies.set("pitchcopytrade_session", build_session_cookie_value(user))
        client.cookies.set("pitchcopytrade_session_staff_mode", "author")
        response = client.post("/auth/mode", data={"mode": "admin", "next": "/author/recommendations"}, follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/admin/dashboard"
        assert "pitchcopytrade_session_staff_mode=admin" in response.headers["set-cookie"]


def test_dual_role_mode_resolution_defaults_to_admin() -> None:
    user = _make_dual_role_user()
    assert resolve_staff_mode(user, None) == "admin"


def test_dual_role_mode_resolution_accepts_author() -> None:
    user = _make_dual_role_user()
    assert resolve_staff_mode(user, "author") == "author"


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
        assert response.headers["location"] == "/app/catalog"
        assert f"{get_telegram_fallback_cookie_name()}=" in response.headers["set-cookie"]


def test_tg_auth_respects_safe_next_redirect() -> None:
    repository = FakeAuthRepository()
    user = _make_user()
    repository.users_by_id[user.id] = user

    with _build_client(repository) as client:
        response = client.get(
            "/tg-auth",
            params={"token": build_telegram_login_link_token(user), "next": "/app/catalog"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/app/catalog"


def test_workspace_session_does_not_open_subscriber_feed() -> None:
    repository = FakeAuthRepository()
    user = _make_user()
    repository.users_by_id[user.id] = user

    with _build_client(repository) as client:
        client.cookies.set("pitchcopytrade_session", build_session_cookie_value(user))
        response = client.get("/app/feed", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"].startswith("/verify/telegram?next=/app/catalog&requested_next=/app/feed")


def test_app_home_renders_bootstrap_page() -> None:
    repository = FakeAuthRepository()

    with _build_client(repository) as client:
        response = client.get("/app")

        assert response.status_code == 200
        assert "Открываем каталог стратегий" in response.text
        assert "Открыть Telegram" in response.text


def test_app_home_redirects_to_catalog_with_telegram_cookie() -> None:
    repository = FakeAuthRepository()
    user = _make_user()
    user.telegram_user_id = 12345
    repository.users_by_id[user.id] = user
    repository.users_by_telegram_id[12345] = user

    with _build_client(repository) as client:
        client.cookies.set(get_telegram_fallback_cookie_name(), build_telegram_fallback_cookie_value(user))
        response = client.get("/app", follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/app/catalog"


def test_verify_telegram_page_renders() -> None:
    repository = FakeAuthRepository()

    with _build_client(repository) as client:
        response = client.get("/verify/telegram?requested_next=/app/help")

        assert response.status_code == 200
        assert "Подтверждение через" in response.text
        assert "После подтверждения откроется каталог стратегий" in response.text
        assert "Открыть бота" in response.text
        assert "/app/catalog" in response.text
        assert "requested_next" not in response.text
        assert "/app/help" not in response.text
        assert "Открыть Mini App" in response.text


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
    assert "pct_journey_id=" in response.headers["set-cookie"]
    reset_settings_cache()


def test_tg_webapp_auth_redirects_to_canonical_catalog(monkeypatch) -> None:
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
            data={"init_data": init_data, "next": "/app/catalog"},
        )

        assert response.status_code == 200
        assert response.json()["redirect_url"] == "/app/catalog"
        assert f"{get_telegram_fallback_cookie_name()}=" in response.headers["set-cookie"]
        assert "pct_journey_id=" in response.headers["set-cookie"]
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
