from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.api.deps.repositories import get_auth_repository
from pitchcopytrade.api.deps.repositories import get_optional_db_session
from pitchcopytrade.auth.passwords import hash_password
from pitchcopytrade.auth.roles import get_user_role_slugs
from pitchcopytrade.auth.staff_mode import get_staff_mode_cookie_name, resolve_staff_mode
from pitchcopytrade.auth.session import build_session_cookie_value, build_telegram_fallback_cookie_value
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.enums import RoleSlug, UserStatus
from pitchcopytrade.repositories.contracts import AuthRepository
from pitchcopytrade.repositories.auth import FileAuthRepository
from pitchcopytrade.services.admin import StaffCreateData, StaffUpdateData, create_admin_staff_user, update_admin_staff_user
from pitchcopytrade.web.templates import templates


router = APIRouter(prefix="/dev", tags=["dev"])

DEV_BOOTSTRAP_EMAIL = "dev-superuser@pitchcopytrade.local"
DEV_BOOTSTRAP_DISPLAY_NAME = "Local Dev Superuser"
DEV_BOOTSTRAP_PASSWORD = "local-dev-password"
DEV_BOOTSTRAP_TELEGRAM_ID = 999000099
DEV_BOOTSTRAP_ROLES = (RoleSlug.ADMIN, RoleSlug.AUTHOR, RoleSlug.MODERATOR)


@router.get("", include_in_schema=False)
async def dev_root() -> Response:
    return RedirectResponse(url="/dev/bootstrap", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/bootstrap", response_class=HTMLResponse, include_in_schema=False)
async def dev_bootstrap_page(request: Request) -> Response:
    if not _is_local_dev_bootstrap_allowed():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return templates.TemplateResponse(
        request,
        "dev/bootstrap.html",
        {
            "title": "Local Dev Bootstrap",
            "bootstrap_email": DEV_BOOTSTRAP_EMAIL,
            "bootstrap_password": DEV_BOOTSTRAP_PASSWORD,
            "bootstrap_telegram_id": DEV_BOOTSTRAP_TELEGRAM_ID,
            "modes": _bootstrap_modes(),
        },
    )


@router.post("/bootstrap", include_in_schema=False)
async def dev_bootstrap_submit(
    _request: Request,
    mode: str = Form("admin"),
    auth_repository: AuthRepository = Depends(get_auth_repository),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    if not _is_local_dev_bootstrap_allowed():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    user = await _ensure_local_staff_user(auth_repository, session)
    desired_mode = _normalize_mode(mode)
    active_staff_mode = resolve_staff_mode(user, desired_mode if desired_mode in {"admin", "author", "moderator"} else "admin")
    redirect_url = _bootstrap_redirect_url(desired_mode, active_staff_mode)

    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    _set_dev_bootstrap_cookies(response, user, active_staff_mode)
    return response


async def _ensure_local_staff_user(
    auth_repository: AuthRepository,
    session: AsyncSession | None,
) -> User:
    desired_roles = set(DEV_BOOTSTRAP_ROLES)
    existing_user = await auth_repository.get_user_by_identity(DEV_BOOTSTRAP_EMAIL)
    if existing_user is None:
        existing_user = await auth_repository.get_user_by_telegram_id(DEV_BOOTSTRAP_TELEGRAM_ID)

    if existing_user is None:
        user = await create_admin_staff_user(
            session,
            StaffCreateData(
                display_name=DEV_BOOTSTRAP_DISPLAY_NAME,
                email=DEV_BOOTSTRAP_EMAIL,
                telegram_user_id=DEV_BOOTSTRAP_TELEGRAM_ID,
                role_slugs=DEV_BOOTSTRAP_ROLES,
            ),
            skip_invite=True,
        )
    else:
        user = existing_user
        if get_user_role_slugs(user) != desired_roles or user.author_profile is None:
            user = await update_admin_staff_user(
                session,
                actor_user_id=user.id,
                user_id=user.id,
                data=StaffUpdateData(
                    display_name=DEV_BOOTSTRAP_DISPLAY_NAME,
                    email=DEV_BOOTSTRAP_EMAIL,
                    telegram_user_id=DEV_BOOTSTRAP_TELEGRAM_ID,
                    role_slugs=DEV_BOOTSTRAP_ROLES,
                ),
            )

    if session is None:
        auth_repository = FileAuthRepository()
        reloaded_user = await auth_repository.get_user_by_identity(DEV_BOOTSTRAP_EMAIL)
        if reloaded_user is None:
            reloaded_user = await auth_repository.get_user_by_telegram_id(DEV_BOOTSTRAP_TELEGRAM_ID)
        if reloaded_user is None:
            raise RuntimeError("Local dev bootstrap user was not persisted")
        user = reloaded_user

    user.full_name = DEV_BOOTSTRAP_DISPLAY_NAME
    user.email = DEV_BOOTSTRAP_EMAIL
    user.telegram_user_id = DEV_BOOTSTRAP_TELEGRAM_ID
    user.password_hash = hash_password(DEV_BOOTSTRAP_PASSWORD)
    user.status = UserStatus.ACTIVE
    await auth_repository.commit()
    return user


def _set_dev_bootstrap_cookies(response: Response, user: User, staff_mode: str) -> None:
    settings = get_settings()
    secure = settings.app.base_url.startswith("https://")
    response.set_cookie(
        key=settings.auth.session_cookie_name,
        value=build_session_cookie_value(user),
        httponly=True,
        max_age=settings.auth.session_ttl_seconds,
        samesite="strict",
        secure=secure,
        path="/",
    )
    response.set_cookie(
        key=get_staff_mode_cookie_name(),
        value=staff_mode,
        httponly=True,
        max_age=settings.auth.session_ttl_seconds,
        samesite="strict",
        secure=secure,
        path="/",
    )
    response.set_cookie(
        key=f"{settings.auth.session_cookie_name}_tg",
        value=build_telegram_fallback_cookie_value(user),
        httponly=True,
        max_age=settings.auth.session_ttl_seconds,
        samesite="strict",
        secure=secure,
        path="/",
    )


def _bootstrap_redirect_url(mode: str, active_staff_mode: str) -> str:
    if mode in {"catalog", "app"}:
        return "/app/catalog"
    if mode == "author":
        return "/author/dashboard"
    if mode == "moderator":
        return "/moderation/queue"
    if active_staff_mode == "author":
        return "/author/dashboard"
    if active_staff_mode == "moderator":
        return "/moderation/queue"
    return "/admin/dashboard"


def _bootstrap_modes() -> list[dict[str, str]]:
    return [
        {
            "value": "admin",
            "label": "Admin",
            "description": "Откроет /admin/dashboard и оставит Mini App cookie активным.",
        },
        {
            "value": "author",
            "label": "Author",
            "description": "Откроет /author/dashboard и сохранит доступ к /app/*.",
        },
        {
            "value": "moderator",
            "label": "Moderator",
            "description": "Откроет /moderation/queue и сохранит доступ к /app/*.",
        },
        {
            "value": "catalog",
            "label": "Catalog",
            "description": "Откроет /app/catalog как стартовую Mini App surface.",
        },
    ]


def _normalize_mode(mode: str) -> str:
    normalized = (mode or "").strip().lower()
    if normalized in {"admin", "author", "moderator", "catalog", "app"}:
        return normalized
    return "admin"


def _is_local_dev_bootstrap_allowed() -> bool:
    settings = get_settings()
    return settings.app.env.lower() in {"development", "local", "test"}
