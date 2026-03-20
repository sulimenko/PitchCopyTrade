from __future__ import annotations

from urllib.parse import urlencode

from pitchcopytrade.auth.roles import get_user_role_slugs
from pitchcopytrade.auth.tokens import (
    AuthTokenError,
    create_staff_invite_token,
    create_session_token,
    create_telegram_login_token,
    decode_staff_invite_token,
    decode_session_token,
    decode_telegram_login_token,
)
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.repositories.contracts import AuthRepository


def build_session_cookie_value(user: User) -> str:
    settings = get_settings()
    return create_session_token(
        user_id=user.id,
        role_slugs=get_user_role_slugs(user),
        secret_key=settings.app.secret_key.get_secret_value(),
        ttl_seconds=settings.auth.session_ttl_seconds,
    )


def decode_session_cookie_value(token: str):
    settings = get_settings()
    return decode_session_token(token, secret_key=settings.app.secret_key.get_secret_value())


def get_telegram_fallback_cookie_name() -> str:
    settings = get_settings()
    return f"{settings.auth.session_cookie_name}_tg"


def build_telegram_fallback_cookie_value(user: User) -> str:
    settings = get_settings()
    return create_telegram_login_token(
        user_id=user.id,
        secret_key=settings.app.secret_key.get_secret_value(),
        ttl_seconds=settings.auth.session_ttl_seconds,
    )


def build_telegram_login_link_token(user: User) -> str:
    settings = get_settings()
    return create_telegram_login_token(
        user_id=user.id,
        secret_key=settings.app.secret_key.get_secret_value(),
    )


def decode_telegram_login_link_token(token: str):
    settings = get_settings()
    return decode_telegram_login_token(token, secret_key=settings.app.secret_key.get_secret_value())


def build_staff_invite_token(user: User) -> str:
    settings = get_settings()
    return create_staff_invite_token(
        user_id=user.id,
        version=max(int(getattr(user, "invite_token_version", 1) or 1), 1),
        secret_key=settings.app.secret_key.get_secret_value(),
    )


def build_staff_invite_link(user: User) -> str:
    settings = get_settings()
    base_url = settings.app.base_url.rstrip("/")
    query = urlencode({"invite_token": build_staff_invite_token(user)})
    return f"{base_url}/login?{query}"


def decode_staff_invite_link_token(token: str):
    settings = get_settings()
    return decode_staff_invite_token(token, secret_key=settings.app.secret_key.get_secret_value())


async def get_user_from_session_token(repository: AuthRepository, token: str) -> User | None:
    try:
        payload = decode_session_cookie_value(token)
    except AuthTokenError:
        return None
    return await repository.get_user_by_id(payload.subject)


async def get_user_from_telegram_login_token(repository: AuthRepository, token: str) -> User | None:
    try:
        payload = decode_telegram_login_link_token(token)
    except AuthTokenError:
        return None
    return await repository.get_user_by_id(payload.subject)


async def get_user_from_staff_invite_token(repository: AuthRepository, token: str) -> User | None:
    try:
        payload = decode_staff_invite_link_token(token)
    except AuthTokenError:
        return None
    user = await repository.get_user_by_id(payload.subject)
    if user is None:
        return None
    if (payload.version or 1) != max(int(getattr(user, "invite_token_version", 1) or 1), 1):
        return None
    return user


async def get_user_from_telegram_fallback_cookie(repository: AuthRepository, token: str) -> User | None:
    return await get_user_from_telegram_login_token(repository, token)
