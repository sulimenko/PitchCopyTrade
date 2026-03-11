from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.auth.roles import get_user_role_slugs
from pitchcopytrade.auth.tokens import (
    AuthTokenError,
    create_session_token,
    create_telegram_login_token,
    decode_session_token,
    decode_telegram_login_token,
)
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.models.accounts import User


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


async def get_user_from_session_token(session: AsyncSession, token: str) -> User | None:
    try:
        payload = decode_session_cookie_value(token)
    except AuthTokenError:
        return None

    query = (
        select(User)
        .options(selectinload(User.roles), selectinload(User.author_profile))
        .where(User.id == payload.subject)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_user_from_telegram_login_token(session: AsyncSession, token: str) -> User | None:
    try:
        payload = decode_telegram_login_link_token(token)
    except AuthTokenError:
        return None

    query = (
        select(User)
        .options(selectinload(User.roles), selectinload(User.author_profile))
        .where(User.id == payload.subject)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_user_from_telegram_fallback_cookie(session: AsyncSession, token: str) -> User | None:
    return await get_user_from_telegram_login_token(session, token)
