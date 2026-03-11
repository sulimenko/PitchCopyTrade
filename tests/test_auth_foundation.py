from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pitchcopytrade.auth.passwords import hash_password, verify_password
from pitchcopytrade.auth.roles import get_user_role_slugs, require_any_role, user_has_role
from pitchcopytrade.auth.tokens import AuthTokenError, create_session_token, decode_session_token
from pitchcopytrade.db.models.accounts import Role, User
from pitchcopytrade.db.models.enums import RoleSlug


def test_hash_password_and_verify_roundtrip() -> None:
    password_hash = hash_password("strong-password")

    assert password_hash.startswith("scrypt$")
    assert verify_password("strong-password", password_hash) is True
    assert verify_password("wrong-password", password_hash) is False


def test_hash_password_rejects_empty_password() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        hash_password("")


def test_session_token_roundtrip() -> None:
    now = datetime(2026, 3, 11, tzinfo=timezone.utc)
    token = create_session_token(
        user_id="user-1",
        role_slugs={RoleSlug.ADMIN, RoleSlug.AUTHOR},
        secret_key="secret-key",
        ttl_seconds=600,
        now=now,
    )

    payload = decode_session_token(token, secret_key="secret-key", now=now + timedelta(seconds=10))

    assert payload.subject == "user-1"
    assert set(payload.roles) == {RoleSlug.ADMIN, RoleSlug.AUTHOR}
    assert payload.token_type == "session"


def test_session_token_detects_expiry() -> None:
    now = datetime(2026, 3, 11, tzinfo=timezone.utc)
    token = create_session_token(
        user_id="user-1",
        role_slugs={RoleSlug.AUTHOR},
        secret_key="secret-key",
        ttl_seconds=10,
        now=now,
    )

    with pytest.raises(AuthTokenError, match="expired"):
        decode_session_token(token, secret_key="secret-key", now=now + timedelta(seconds=11))


def test_user_role_mapping_helpers() -> None:
    user = User(username="alex")
    user.roles = [
        Role(slug=RoleSlug.ADMIN, title="Admin"),
        Role(slug=RoleSlug.AUTHOR, title="Author"),
    ]

    assert get_user_role_slugs(user) == {RoleSlug.ADMIN, RoleSlug.AUTHOR}
    assert user_has_role(user, RoleSlug.AUTHOR) is True
    require_any_role(user, {RoleSlug.MODERATOR, RoleSlug.AUTHOR})

    with pytest.raises(PermissionError, match="required role"):
        require_any_role(user, {RoleSlug.MODERATOR})
