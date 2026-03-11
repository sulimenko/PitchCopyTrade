from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from pitchcopytrade.auth.roles import require_any_role
from pitchcopytrade.auth.session import (
    get_telegram_fallback_cookie_name,
    get_user_from_session_token,
    get_user_from_telegram_fallback_cookie,
)
from pitchcopytrade.api.deps.repositories import get_auth_repository
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.enums import RoleSlug
from pitchcopytrade.repositories.contracts import AuthRepository


async def get_current_staff_user(request: Request, repository: AuthRepository = Depends(get_auth_repository)) -> User:
    settings = get_settings()
    token = request.cookies.get(settings.auth.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    user = await get_user_from_session_token(repository, token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    return user


async def get_current_subscriber_user(
    request: Request,
    repository: AuthRepository = Depends(get_auth_repository),
) -> User:
    token = request.cookies.get(get_telegram_fallback_cookie_name())
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram authentication required")

    user = await get_user_from_telegram_fallback_cookie(repository, token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram access")

    return user


async def require_admin(user: User = Depends(get_current_staff_user)) -> User:
    try:
        require_any_role(user, {RoleSlug.ADMIN})
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return user


async def require_author(user: User = Depends(get_current_staff_user)) -> User:
    try:
        require_any_role(user, {RoleSlug.AUTHOR})
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if user.author_profile is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Author profile is not configured")
    return user


async def require_moderator(user: User = Depends(get_current_staff_user)) -> User:
    try:
        require_any_role(user, {RoleSlug.MODERATOR})
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return user
