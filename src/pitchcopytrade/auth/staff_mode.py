from __future__ import annotations

from fastapi import HTTPException, Request, status

from pitchcopytrade.auth.roles import get_user_role_slugs
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.enums import RoleSlug

STAFF_MODE_ADMIN = "admin"
STAFF_MODE_AUTHOR = "author"
STAFF_MODE_MODERATOR = "moderator"


def get_staff_mode_cookie_name() -> str:
    settings = get_settings()
    return f"{settings.auth.session_cookie_name}_staff_mode"


def get_allowed_staff_modes(user: User) -> set[str]:
    role_slugs = get_user_role_slugs(user)
    allowed: set[str] = set()
    if RoleSlug.ADMIN in role_slugs:
        allowed.add(STAFF_MODE_ADMIN)
    if RoleSlug.AUTHOR in role_slugs:
        allowed.add(STAFF_MODE_AUTHOR)
    if RoleSlug.MODERATOR in role_slugs:
        allowed.add(STAFF_MODE_MODERATOR)
    return allowed


def resolve_staff_mode(user: User, requested_mode: str | None = None) -> str:
    allowed = get_allowed_staff_modes(user)
    normalized = (requested_mode or "").strip().lower()
    if normalized in allowed:
        return normalized
    if STAFF_MODE_ADMIN in allowed:
        return STAFF_MODE_ADMIN
    if STAFF_MODE_AUTHOR in allowed:
        return STAFF_MODE_AUTHOR
    if STAFF_MODE_MODERATOR in allowed:
        return STAFF_MODE_MODERATOR
    return ""


def get_active_staff_mode(request: Request, user: User) -> str:
    return resolve_staff_mode(user, request.cookies.get(get_staff_mode_cookie_name()))


def require_staff_mode(request: Request, user: User, expected_mode: str) -> str:
    active_mode = get_active_staff_mode(request, user)
    allowed = get_allowed_staff_modes(user)
    if expected_mode not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав для этого режима")
    if len(allowed) > 1 and active_mode != expected_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Переключитесь в режим {expected_mode} для доступа к этому разделу",
        )
    return active_mode
