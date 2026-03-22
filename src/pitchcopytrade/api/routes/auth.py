from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.responses import Response
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from urllib.parse import urlparse

from pitchcopytrade.api.deps.repositories import get_public_repository
from pitchcopytrade.api.deps.repositories import get_auth_repository
from pitchcopytrade.auth.telegram_login_widget import TelegramLoginWidgetError, verify_telegram_login_widget
from pitchcopytrade.auth.telegram_webapp import (
    TelegramWebAppAuthError,
    extract_telegram_webapp_profile,
    validate_telegram_webapp_init_data,
)
from pitchcopytrade.auth.roles import get_user_role_slugs
from pitchcopytrade.auth.service import authenticate_user
from pitchcopytrade.auth.staff_mode import get_staff_mode_cookie_name, resolve_staff_mode
from pitchcopytrade.auth.session import (
    build_staff_invite_bot_link,
    build_staff_invite_help_bot_link,
    build_session_cookie_value,
    build_telegram_fallback_cookie_value,
    get_telegram_fallback_cookie_name,
    get_user_from_staff_invite_token,
    get_user_from_session_token,
    get_user_from_telegram_fallback_cookie,
    get_user_from_telegram_login_token,
)
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.models.enums import RoleSlug, UserStatus
from pitchcopytrade.repositories.contracts import AuthRepository
from pitchcopytrade.repositories.contracts import PublicRepository
from pitchcopytrade.services.public import TelegramSubscriberProfile, upsert_telegram_subscriber
from pitchcopytrade.web.templates import templates


router = APIRouter(tags=["auth"])


@router.get("/auth/login", response_class=HTMLResponse, include_in_schema=False)
async def auth_login_page(request: Request, repository: AuthRepository = Depends(get_auth_repository)) -> Response:
    return await login_page(request, repository)


@router.get("/auth/telegram/callback", response_class=HTMLResponse, include_in_schema=False)
async def telegram_widget_callback(
    request: Request,
    repository: AuthRepository = Depends(get_auth_repository),
) -> Response:
    settings = get_settings()
    params = dict(request.query_params)
    invite_token = str(request.query_params.get("invite_token", "") or "")
    auth_params = {key: value for key, value in params.items() if key != "invite_token"}

    try:
        verify_telegram_login_widget(
            auth_params,
            bot_token=settings.telegram.bot_token.get_secret_value(),
            max_age_seconds=300,
        )
    except TelegramLoginWidgetError:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            _build_login_template_context(title="Вход", error="Ошибка авторизации Telegram"),
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        telegram_user_id = int(params.get("id", "0"))
    except ValueError:
        telegram_user_id = 0

    user = await repository.get_user_by_telegram_id(telegram_user_id)
    if user is not None and user.status != UserStatus.ACTIVE:
        user = None
    if invite_token:
        try:
            bound_user = await _bind_staff_user_by_invite_token(repository, invite_token, telegram_user_id)
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "auth/login.html",
                _build_login_template_context(
                    title="Вход в PitchCopyTrade",
                    error=str(exc),
                    invite_token=invite_token,
                ),
                status_code=status.HTTP_409_CONFLICT,
            )
        if bound_user is not None:
            user = bound_user
    if user is None:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            _build_login_template_context(
                title="Вход в PitchCopyTrade",
                error="Пользователь с таким Telegram ID не найден среди сотрудников",
                invite_token=invite_token,
            ),
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    redirect_url, staff_mode = _resolve_role_redirect(user, request.cookies.get(get_staff_mode_cookie_name()))
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    _set_staff_session_cookies(response, user, staff_mode)
    return response


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, repository: AuthRepository = Depends(get_auth_repository)) -> Response:
    token = request.cookies.get(get_settings().auth.session_cookie_name)
    user = await get_user_from_session_token(repository, token) if token else None
    if user is not None and user.status == UserStatus.ACTIVE:
        redirect_url, _staff_mode = _resolve_role_redirect(user, request.cookies.get(get_staff_mode_cookie_name()))
        return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    tg_token = request.cookies.get(get_telegram_fallback_cookie_name())
    tg_user = await get_user_from_telegram_fallback_cookie(repository, tg_token) if tg_token else None
    if tg_user is not None:
        return RedirectResponse(url="/app/status", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request,
        "auth/login.html",
        _build_login_template_context(
            title="Вход в PitchCopyTrade",
            invite_token=str(request.query_params.get("invite_token", "") or ""),
        ),
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
            _build_login_template_context(
                title="Вход в PitchCopyTrade",
                error="Неверный логин или пароль",
                identity=identity.strip(),
                invite_token=str(request.query_params.get("invite_token", "") or ""),
            ),
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    if user.status != UserStatus.ACTIVE:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            _build_login_template_context(
                title="Вход в PitchCopyTrade",
                error="Staff-аккаунт ещё не активирован. Завершите вход через Telegram invite link.",
                identity=identity.strip(),
                invite_token=str(request.query_params.get("invite_token", "") or ""),
            ),
            status_code=status.HTTP_403_FORBIDDEN,
        )

    redirect_url, staff_mode = _resolve_role_redirect(user, request.cookies.get(get_staff_mode_cookie_name()))
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    _set_staff_session_cookies(response, user, staff_mode)
    return response


@router.get("/logout", include_in_schema=False)
async def logout() -> Response:
    settings = get_settings()
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(settings.auth.session_cookie_name, path="/")
    response.delete_cookie(get_staff_mode_cookie_name(), path="/")
    response.delete_cookie(get_telegram_fallback_cookie_name(), path="/")
    return response


@router.post("/auth/mode", include_in_schema=False)
async def switch_staff_mode(
    request: Request,
    mode: str = Form(...),
    next: str = Form("/workspace"),
    repository: AuthRepository = Depends(get_auth_repository),
) -> Response:
    user = await _require_authenticated_user(request, repository)
    staff_mode = resolve_staff_mode(user, mode)
    if staff_mode != mode.strip().lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недопустимый режим")
    response = RedirectResponse(url=_canonical_staff_home(staff_mode), status_code=status.HTTP_303_SEE_OTHER)
    _set_staff_session_cookies(response, user, staff_mode)
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
    timezone_name: str = Form("Europe/Moscow"),
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
            timezone_name=timezone_name.strip() or "Europe/Moscow",
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
            return RedirectResponse(url="/app/status", status_code=status.HTTP_303_SEE_OTHER)

    try:
        user = await _require_authenticated_user(request, repository)
    except HTTPException:
        # Не перенаправляем на /login — в Telegram Mini App WebView он не работает.
        # Показываем landing-страницу: JS автоматически шлёт initData → авторизует → перенаправляет.
        return templates.TemplateResponse(
            request,
            "app/miniapp_entry.html",
            {"title": "PitchCopyTrade", "login_url": "/login"},
        )

    redirect_url, _staff_mode = _resolve_role_redirect(user, request.cookies.get(get_staff_mode_cookie_name()))
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


def _resolve_role_redirect(user, requested_mode: str | None = None) -> tuple[str, str]:
    role_labels = {role.value for role in get_user_role_slugs(user)}
    staff_mode = resolve_staff_mode(user, requested_mode)
    if RoleSlug.ADMIN.value in role_labels and staff_mode == "admin":
        return "/admin/dashboard", staff_mode
    if RoleSlug.AUTHOR.value in role_labels and staff_mode == "author":
        return "/author/dashboard", staff_mode
    if RoleSlug.AUTHOR.value in role_labels:
        return "/author/dashboard", staff_mode
    if RoleSlug.MODERATOR.value in role_labels:
        return "/moderation/queue", staff_mode
    return "/login", staff_mode


def _sanitize_subscriber_next_path(next_path: str | None) -> str:
    if not next_path:
        return "/app/status"
    if not next_path.startswith("/") or next_path.startswith("//"):
        return "/app/status"
    return next_path


def _build_login_template_context(
    *,
    title: str,
    error: str | None = None,
    identity: str = "",
    invite_token: str = "",
) -> dict[str, object]:
    settings = get_settings()
    base_url = settings.app.base_url.rstrip("/")
    parsed = urlparse(base_url)
    login_domain = parsed.hostname or ""
    telegram_auth_url = f"{base_url}/auth/telegram/callback"
    if invite_token:
        telegram_auth_url = f"{telegram_auth_url}?invite_token={invite_token}"
    return {
        "title": title,
        "error": error,
        "identity": identity,
        "invite_token": invite_token,
        "is_staff_invite": bool(invite_token),
        "bot_username": settings.telegram.bot_username,
        "telegram_auth_url": telegram_auth_url,
        "telegram_login_domain": login_domain,
        "telegram_https_ready": parsed.scheme == "https",
        "telegram_bot_username": settings.telegram.bot_username,
        "subscriber_verify_url": "/verify/telegram",
        "invite_link_url": f"{base_url}/login?invite_token={invite_token}" if invite_token else "",
        "telegram_invite_bot_url": build_staff_invite_bot_link(invite_token) if invite_token else "",
        "telegram_request_invite_url": build_staff_invite_help_bot_link(invite_token) if invite_token else "",
    }


async def _require_authenticated_user(request: Request, repository: AuthRepository):
    settings = get_settings()
    token = request.cookies.get(settings.auth.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    user = await get_user_from_session_token(repository, token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff account is not activated")
    return user


async def _bind_staff_user_by_invite_token(
    repository: AuthRepository,
    invite_token: str,
    telegram_user_id: int,
):
    invited_user = await get_user_from_staff_invite_token(repository, invite_token)
    if invited_user is None:
        raise ValueError("Приглашение недействительно или устарело.")
    existing_user = await repository.get_user_by_telegram_id(telegram_user_id)
    if existing_user is not None and existing_user.id != invited_user.id:
        raise ValueError("Этот Telegram-аккаунт уже привязан к другому сотруднику.")
    if invited_user.telegram_user_id not in (None, telegram_user_id):
        raise ValueError("Приглашение уже связано с другим Telegram-аккаунтом.")
    invited_user.telegram_user_id = telegram_user_id
    invited_user.status = UserStatus.ACTIVE
    await repository.commit()
    return invited_user


def _set_staff_session_cookies(response: Response, user, staff_mode: str) -> None:
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


def _canonical_staff_home(staff_mode: str) -> str:
    if staff_mode == "admin":
        return "/admin/dashboard"
    if staff_mode == "author":
        return "/author/dashboard"
    if staff_mode == "moderator":
        return "/moderation/queue"
    return "/workspace"
