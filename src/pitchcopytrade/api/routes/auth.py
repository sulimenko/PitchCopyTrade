from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.responses import Response
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse

from pitchcopytrade.api.deps.repositories import get_public_repository
from pitchcopytrade.api.deps.repositories import get_auth_repository
from pitchcopytrade.auth.telegram_webapp import (
    TelegramWebAppAuthError,
    extract_telegram_webapp_profile,
    validate_telegram_webapp_init_data,
)
from pitchcopytrade.auth.roles import get_user_role_slugs
from pitchcopytrade.auth.service import authenticate_user
from pitchcopytrade.auth.session import (
    build_session_cookie_value,
    build_telegram_fallback_cookie_value,
    get_telegram_fallback_cookie_name,
    get_user_from_session_token,
    get_user_from_telegram_fallback_cookie,
    get_user_from_telegram_login_token,
)
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.models.enums import RoleSlug
from pitchcopytrade.repositories.contracts import AuthRepository
from pitchcopytrade.repositories.contracts import PublicRepository
from pitchcopytrade.services.public import TelegramSubscriberProfile, upsert_telegram_subscriber
from pitchcopytrade.web.templates import templates


router = APIRouter(tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, repository: AuthRepository = Depends(get_auth_repository)) -> Response:
    token = request.cookies.get(get_settings().auth.session_cookie_name)
    user = await get_user_from_session_token(repository, token) if token else None
    if user is not None:
        return RedirectResponse(url=_resolve_role_redirect(user), status_code=status.HTTP_303_SEE_OTHER)
    tg_token = request.cookies.get(get_telegram_fallback_cookie_name())
    tg_user = await get_user_from_telegram_fallback_cookie(repository, tg_token) if tg_token else None
    if tg_user is not None:
        return RedirectResponse(url="/app/feed", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {
            "title": "Вход в PitchCopyTrade",
            "error": None,
            "identity": "",
        },
    )


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    identity: str = Form(...),
    password: str = Form(...),
    repository: AuthRepository = Depends(get_auth_repository),
) -> Response:
    user = await authenticate_user(repository, identity.strip(), password)
    if user is None:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "title": "Вход в PitchCopyTrade",
                "error": "Неверный логин или пароль",
                "identity": identity.strip(),
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    settings = get_settings()
    response = RedirectResponse(url=_resolve_role_redirect(user), status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key=settings.auth.session_cookie_name,
        value=build_session_cookie_value(user),
        httponly=True,
        max_age=settings.auth.session_ttl_seconds,
        samesite="lax",
        secure=settings.app.base_url.startswith("https://"),
        path="/",
    )
    return response


@router.get("/logout", include_in_schema=False)
async def logout() -> Response:
    settings = get_settings()
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(settings.auth.session_cookie_name, path="/")
    response.delete_cookie(get_telegram_fallback_cookie_name(), path="/")
    return response


@router.get("/tg-auth", include_in_schema=False)
async def telegram_auth_login(
    token: str,
    next: str | None = None,
    repository: AuthRepository = Depends(get_auth_repository),
) -> Response:
    user = await get_user_from_telegram_login_token(repository, token)
    if user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    settings = get_settings()
    response = RedirectResponse(url=_sanitize_subscriber_next_path(next), status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key=get_telegram_fallback_cookie_name(),
        value=build_telegram_fallback_cookie_value(user),
        httponly=True,
        max_age=settings.auth.session_ttl_seconds,
        samesite="lax",
        secure=settings.app.base_url.startswith("https://"),
        path="/",
    )
    return response


@router.post("/tg-webapp/auth", include_in_schema=False)
async def telegram_webapp_auth(
    init_data: str = Form(...),
    next: str = Form("/app/status"),
    repository: PublicRepository = Depends(get_public_repository),
) -> Response:
    settings = get_settings()
    try:
        validated = validate_telegram_webapp_init_data(
            init_data,
            bot_token=settings.telegram.bot_token.get_secret_value(),
            max_age_seconds=min(settings.auth.session_ttl_seconds, 3600),
        )
        profile = extract_telegram_webapp_profile(validated)
    except TelegramWebAppAuthError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_401_UNAUTHORIZED)

    user = await upsert_telegram_subscriber(
        repository,
        TelegramSubscriberProfile(
            telegram_user_id=profile.telegram_user_id,
            username=profile.username,
            first_name=profile.first_name,
            last_name=profile.last_name,
        ),
    )
    await repository.commit()

    response = JSONResponse({"redirect_url": _sanitize_subscriber_next_path(next)})
    response.set_cookie(
        key=get_telegram_fallback_cookie_name(),
        value=build_telegram_fallback_cookie_value(user),
        httponly=True,
        max_age=settings.auth.session_ttl_seconds,
        samesite="lax",
        secure=settings.app.base_url.startswith("https://"),
        path="/",
    )
    return response


@router.get("/app", response_class=HTMLResponse)
async def app_home(request: Request, repository: AuthRepository = Depends(get_auth_repository)) -> Response:
    settings = get_settings()
    tg_token = request.cookies.get(get_telegram_fallback_cookie_name())
    if tg_token:
        subscriber = await get_user_from_telegram_fallback_cookie(repository, tg_token)
        if subscriber is not None:
            return RedirectResponse(url="/app/feed", status_code=status.HTTP_303_SEE_OTHER)

    try:
        user = await _require_authenticated_user(request, repository)
    except HTTPException:
        response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(settings.auth.session_cookie_name, path="/")
        response.delete_cookie(get_telegram_fallback_cookie_name(), path="/")
        return response

    redirect_url = _resolve_role_redirect(user)
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/workspace", response_class=HTMLResponse)
async def workspace_home(request: Request, repository: AuthRepository = Depends(get_auth_repository)) -> Response:
    settings = get_settings()
    try:
        user = await _require_authenticated_user(request, repository)
    except HTTPException:
        response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(settings.auth.session_cookie_name, path="/")
        return response

    role_labels = sorted(role.value for role in get_user_role_slugs(user))
    return templates.TemplateResponse(
        request,
        "auth/app_home.html",
        {
            "title": "PitchCopyTrade Workspace",
            "user": user,
            "role_labels": role_labels,
            "role_home": _resolve_role_home(role_labels),
        },
    )


def _resolve_role_home(role_labels: list[str]) -> str:
    if RoleSlug.ADMIN.value in role_labels:
        return "Admin workspace"
    if RoleSlug.MODERATOR.value in role_labels:
        return "Moderator queue"
    return "Author workspace"


def _resolve_role_redirect(user) -> str:
    role_labels = {role.value for role in get_user_role_slugs(user)}
    if RoleSlug.ADMIN.value in role_labels:
        return "/admin/dashboard"
    if RoleSlug.AUTHOR.value in role_labels:
        return "/author/dashboard"
    if RoleSlug.MODERATOR.value in role_labels:
        return "/moderation/queue"
    return "/login"


def _sanitize_subscriber_next_path(next_path: str | None) -> str:
    if not next_path:
        return "/app/feed"
    if not next_path.startswith("/") or next_path.startswith("//"):
        return "/app/feed"
    return next_path


async def _require_authenticated_user(request: Request, repository: AuthRepository):
    settings = get_settings()
    token = request.cookies.get(settings.auth.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    user = await get_user_from_session_token(repository, token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    return user
