from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from pitchcopytrade.api.deps.repositories import get_access_repository, get_auth_repository
from pitchcopytrade.api.main import create_app
from pitchcopytrade.auth.passwords import hash_password
from pitchcopytrade.auth.session import build_telegram_fallback_cookie_value, get_telegram_fallback_cookie_name
from pitchcopytrade.db.models.accounts import AuthorProfile, Role, User
from pitchcopytrade.db.models.catalog import Instrument, Strategy
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.enums import InstrumentType, RiskLevel, RoleSlug, StrategyStatus, UserStatus
from pitchcopytrade.storage.local import LocalFilesystemStorage


class FakeAuthRepository:
    def __init__(self, user: User) -> None:
        self.user = user

    async def get_user_by_id(self, user_id: str) -> User | None:
        return self.user if self.user.id == user_id else None


class FakeAccessRepository:
    def __init__(self, user: User, message: Message) -> None:
        self.user = user
        self.message = message

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> User | None:
        return self.user if self.user.telegram_user_id == telegram_user_id else None

    async def user_has_active_access(self, user_id: str) -> bool:
        return user_id == self.user.id

    async def list_user_visible_messages(self, *, user_id: str, limit: int = 20) -> list[Message]:
        return [self.message][:limit] if user_id == self.user.id else []

    async def get_user_visible_message(self, *, user_id: str, message_id: str) -> Message | None:
        if user_id != self.user.id or message_id != self.message.id:
            return None
        return self.message

    async def commit(self) -> None:
        return None

    async def list_user_reminder_events(self, *, user_id: str, limit: int = 20):
        return []

    async def get_notification_preferences(self, *, user_id: str) -> dict[str, bool]:
        return {"payment_reminders": True, "subscription_reminders": True}

    async def save_notification_preferences(self, *, user_id: str, preferences: dict[str, bool]) -> dict[str, bool]:
        return {"payment_reminders": True, "subscription_reminders": True}


def _make_user() -> User:
    user = User(
        id="user-1",
        email="lead@example.com",
        full_name="Lead User",
        password_hash=hash_password("checkout-pass"),
        telegram_user_id=12345,
        timezone="Europe/Moscow",
    )
    user.roles = [Role(slug=RoleSlug.AUTHOR, title="Author")]
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
        kind="idea",
        status="published",
        type="mixed",
        title="Покупка SBER",
        text={"body": "<p>Сильный спрос и пробой уровня</p>", "plain": "Сильный спрос и пробой уровня"},
        documents=[
            {
                "id": "doc-1",
                "object_key": "messages/msg-1/file.pdf",
                "original_filename": "idea.pdf",
                "content_type": "application/pdf",
                "size_bytes": 1234,
            }
        ],
        deals=[
            {
                "instrument_id": "SBER",
                "side": "buy",
                "entry_from": "101.5",
                "stop_loss": "99.9",
                "take_profit_1": "106.2",
            }
        ],
        published=datetime(2026, 3, 11, tzinfo=timezone.utc),
    )
    message.strategy = strategy
    message.author = author
    return message


def _build_client(user: User, message: Message) -> TestClient:
    app = create_app()
    auth_repository = FakeAuthRepository(user)
    access_repository = FakeAccessRepository(user, message)

    async def override_auth_repository():
        return auth_repository

    async def override_access_repository():
        return access_repository

    app.dependency_overrides[get_auth_repository] = override_auth_repository
    app.dependency_overrides[get_access_repository] = override_access_repository
    return TestClient(app)


def test_message_feed_renders_visible_message() -> None:
    user = _make_user()
    message = _make_message()
    with _build_client(user, message) as client:
        client.cookies.set(get_telegram_fallback_cookie_name(), build_telegram_fallback_cookie_value(user))
        response = client.get("/app/feed")

        assert response.status_code == 200
        assert "Лента публикаций" in response.text
        assert "Покупка SBER" in response.text
        assert "Сильный спрос и пробой уровня" in response.text


def test_message_detail_renders_documents_and_deals() -> None:
    user = _make_user()
    message = _make_message()
    with _build_client(user, message) as client:
        client.cookies.set(get_telegram_fallback_cookie_name(), build_telegram_fallback_cookie_value(user))
        response = client.get("/app/messages/msg-1")

        assert response.status_code == 200
        assert "История сообщения" in response.text
        assert "Покупка SBER" in response.text
        assert "Deal payload" in response.text
        assert "idea.pdf" in response.text


def test_message_attachment_download(monkeypatch) -> None:
    user = _make_user()
    message = _make_message()
    with _build_client(user, message) as client:
        client.cookies.set(get_telegram_fallback_cookie_name(), build_telegram_fallback_cookie_value(user))
        monkeypatch.setattr(LocalFilesystemStorage, "download_bytes", lambda self, _key: b"pdf-data")
        response = client.get("/app/messages/msg-1/attachments/doc-1")

        assert response.status_code == 200
        assert response.headers["content-disposition"] == 'attachment; filename="idea.pdf"'
        assert response.content == b"pdf-data"
