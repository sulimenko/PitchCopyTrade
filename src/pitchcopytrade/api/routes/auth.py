from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.responses import Response
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from urllib.parse import parse_qs, urlparse

from pitchcopytrade.api.deps.repositories import get_public_repository
from pitchcopytrade.api.deps.repositories import get_auth_repository
from pitchcopytrade.api.request_trace import attach_journey_cookie, get_entry_marker, get_or_create_journey_id, log_request_trace
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


logger = logging.getLogger(__name__)

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
    journey_id = get_or_create_journey_id(request)
    auth_user_id = None
    telegram_user_id = None
    token = request.cookies.get(get_settings().auth.session_cookie_name)
    if token:
        user = await get_user_from_session_token(repository, token)
        if user is not None:
            auth_user_id = user.id
            telegram_user_id = user.telegram_user_id
    log_request_trace(
        logger,
        request,
        stage="login_page",
        journey_id=journey_id,
        surface="bootstrap",
        auth_user_id=auth_user_id,
        telegram_user_id=telegram_user_id,
    )
    user = await get_user_from_session_token(repository, token) if token else None
    if user is not None and user.status == UserStatus.ACTIVE:
        redirect_url, _staff_mode = _resolve_role_redirect(user, request.cookies.get(get_staff_mode_cookie_name()))
        response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
        return attach_journey_cookie(response, journey_id)
    tg_token = request.cookies.get(get_telegram_fallback_cookie_name())
    tg_user = await get_user_from_telegram_fallback_cookie(repository, tg_token) if tg_token else None
    if tg_user is not None:
        response = RedirectResponse(url="/app/catalog", status_code=status.HTTP_303_SEE_OTHER)
        return attach_journey_cookie(response, journey_id)

    response = templates.TemplateResponse(
        request,
        "auth/login.html",
        _build_login_template_context(
            title="Вход в PitchCopyTrade",
            invite_token=str(request.query_params.get("invite_token", "") or ""),
        ),
    )
    return attach_journey_cookie(response, journey_id)


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
    request: Request,
    init_data: str = Form(""),
    next: str = Form("/app/catalog"),  # Z5: Default to catalog for better UX
    timezone_name: str = Form("Europe/Moscow"),
    auth_repository: AuthRepository = Depends(get_auth_repository),
    repository: PublicRepository = Depends(get_public_repository),
) -> Response:
    settings = get_settings()
    journey_id = get_or_create_journey_id(request)
    next_entry_marker = (parse_qs(urlparse(next).query).get("entry") or [None])[0]
    auth_user_id = None
    telegram_user_id = None
    token = request.cookies.get(get_settings().auth.session_cookie_name)
    if token:
        auth_user = await get_user_from_session_token(auth_repository, token)
        if auth_user is not None:
            auth_user_id = auth_user.id
            telegram_user_id = auth_user.telegram_user_id
    log_request_trace(
        logger,
        request,
        stage="tg_webapp_auth_entry",
        journey_id=journey_id,
        surface="bootstrap",
        auth_user_id=auth_user_id,
        telegram_user_id=telegram_user_id,
        entry_marker=next_entry_marker,
        entry_id=journey_id,
        entry_surface="bootstrap",
    )
    try:
        validated = validate_telegram_webapp_init_data(
            init_data,
            bot_token=settings.telegram.bot_token.get_secret_value(),
            max_age_seconds=min(settings.auth.session_ttl_seconds, 3600),
        )
        profile = extract_telegram_webapp_profile(validated)
    except TelegramWebAppAuthError as exc:
        log_request_trace(
            logger,
            request,
            stage="tg_webapp_auth_failed",
            journey_id=journey_id,
            surface="bootstrap",
            auth_user_id=auth_user_id,
            telegram_user_id=telegram_user_id,
            entry_marker=next_entry_marker,
            entry_id=journey_id,
            entry_surface="bootstrap",
            first_html_surface="miniapp_entry",
            requested_next=_sanitize_subscriber_next_path(next),
            block_reason=getattr(exc, "code", "auth_failure"),
            block_detail=str(exc),
        )
        return JSONResponse(
            {"detail": str(exc), "error_code": getattr(exc, "code", "auth_failure")},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

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
    log_request_trace(
        logger,
        request,
        stage="tg_webapp_auth_success",
        journey_id=journey_id,
        surface="bootstrap",
        auth_user_id=auth_user_id,
        telegram_user_id=profile.telegram_user_id,
        entry_marker=next_entry_marker,
        entry_id=journey_id,
        entry_surface="bootstrap",
        first_html_surface="app/catalog",
        requested_next=_sanitize_subscriber_next_path(next),
        rendered_href=_sanitize_subscriber_next_path(next),
    )

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
    return attach_journey_cookie(response, journey_id)


@router.post("/tg-webapp/bootstrap-trace", include_in_schema=False)
async def telegram_webapp_bootstrap_trace(
    request: Request,
    reason: str = Form(...),
    webapp_context_present: str = Form(""),
    auth_repository: AuthRepository = Depends(get_auth_repository),
) -> Response:
    journey_id = get_or_create_journey_id(request)
    auth_user_id = None
    telegram_user_id = None
    token = request.cookies.get(get_settings().auth.session_cookie_name)
    if token:
        auth_user = await get_user_from_session_token(auth_repository, token)
        if auth_user is not None:
            auth_user_id = auth_user.id
            telegram_user_id = auth_user.telegram_user_id
    log_request_trace(
        logger,
        request,
        stage="tg_webapp_bootstrap_trace",
        journey_id=journey_id,
        surface="bootstrap",
        auth_user_id=auth_user_id,
        telegram_user_id=telegram_user_id,
        entry_marker=get_entry_marker(request) or "bot_start",
        entry_id=journey_id,
        entry_surface="bootstrap",
        first_html_surface="miniapp_entry",
        requested_next="/app/catalog",
        block_reason=reason.strip().lower() or "bootstrap_trace",
        rendered_href=reason.strip().lower() or "-",
        webapp_context_present=webapp_context_present.strip().lower() in {"1", "true", "yes"},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/app", response_class=HTMLResponse)
async def app_home(request: Request, repository: AuthRepository = Depends(get_auth_repository)) -> Response:
    journey_id = get_or_create_journey_id(request)
    entry_marker = get_entry_marker(request) or "bot_start"
    tg_token = request.cookies.get(get_telegram_fallback_cookie_name())
    if tg_token:
        subscriber = await get_user_from_telegram_fallback_cookie(repository, tg_token)
        if subscriber is not None:
            log_request_trace(
                logger,
                request,
                stage="app_home_entry",
                journey_id=journey_id,
                surface="bootstrap",
                entry_marker=entry_marker,
                first_html_surface="app/catalog",
                requested_next="/app/catalog",
                rendered_href="/app/catalog",
                block_reason="has_telegram_cookie",
            )
            response = RedirectResponse(url="/app/catalog", status_code=status.HTTP_303_SEE_OTHER)
            return attach_journey_cookie(response, journey_id)

    try:
        user = await _require_authenticated_user(request, repository)
    except HTTPException:
        bot_url = f"https://t.me/{get_settings().telegram.bot_username}"
        log_request_trace(
            logger,
            request,
            stage="app_home_entry",
            journey_id=journey_id,
            surface="bootstrap",
            entry_marker=entry_marker,
            first_html_surface="miniapp_entry",
            requested_next="/app/catalog",
            rendered_href="/app",
            block_reason="no_telegram_cookie",
        )
        response = templates.TemplateResponse(
            request,
            "app/miniapp_entry.html",
            {
                "title": "PitchCopyTrade",
                "telegram_bot_username": get_settings().telegram.bot_username,
                "bot_url": bot_url,
                "next_path": "/app/catalog",
            },
        )
        return attach_journey_cookie(response, journey_id)

    redirect_url, _staff_mode = _resolve_role_redirect(user, request.cookies.get(get_staff_mode_cookie_name()))
    log_request_trace(
        logger,
        request,
        stage="app_home_entry",
        journey_id=journey_id,
        surface="bootstrap",
        entry_marker=entry_marker,
        first_html_surface="app/catalog",
        requested_next="/app/catalog",
        rendered_href=redirect_url,
        block_reason="authenticated_session",
    )
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    return attach_journey_cookie(response, journey_id)


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


# X4: OAuth routes for Google and Yandex (disabled if credentials not configured)


@router.get("/auth/google", include_in_schema=False)
async def google_oauth_start(request: Request) -> Response:
    """X4.4: Redirect to Google OAuth consent screen."""
    from authlib.integrations.httpx_client import AsyncOAuth2Client

    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=404, detail="Google OAuth not configured")

    # Calculate redirect URI
    redirect_uri = f"{settings.app.base_url.rstrip('/')}/auth/google/callback"

    client = AsyncOAuth2Client(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret.get_secret_value(),
        redirect_uri=redirect_uri,
    )

    # Generate authorization URL
    uri, state = client.create_authorization_url(
        "https://accounts.google.com/o/oauth2/v2/auth",
        scope=["openid", "email", "profile"],
    )

    # Store state in cookie for CSRF protection
    response = RedirectResponse(url=uri, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        max_age=600,
        samesite="lax",
        secure=settings.app.base_url.startswith("https://"),
        path="/",
    )
    return response


@router.get("/auth/google/callback", response_class=HTMLResponse, include_in_schema=False)
async def google_oauth_callback(
    request: Request,
    code: str = None,
    state: str = None,
    repository: AuthRepository = Depends(get_auth_repository),
) -> Response:
    """X4.6: Handle Google OAuth callback."""
    from authlib.integrations.httpx_client import AsyncOAuth2Client
    import httpx

    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=404, detail="Google OAuth not configured")

    # Verify state
    stored_state = request.cookies.get("oauth_state")
    if not state or state != stored_state:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            _build_login_template_context(title="PitchCopyTrade", error="OAuth validation failed"),
        )

    redirect_uri = f"{settings.app.base_url.rstrip('/')}/auth/google/callback"

    client = AsyncOAuth2Client(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret.get_secret_value(),
        redirect_uri=redirect_uri,
    )

    try:
        # Exchange code for token
        token = await client.fetch_token("https://oauth2.googleapis.com/token", code=code)

        # Get user info
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {token['access_token']}"},
            )
            user_info = resp.json()

        email = user_info.get("email")
        if not email:
            return templates.TemplateResponse(
                request,
                "auth/login.html",
                _build_login_template_context(title="PitchCopyTrade", error="Could not get email from Google"),
            )

        # X4.6: Find user by email in repository
        user = await repository.get_user_by_identity(email)
        if user is None:
            return templates.TemplateResponse(
                request,
                "auth/login.html",
                _build_login_template_context(title="PitchCopyTrade", error="Email not found in staff directory"),
            )

        # If inactive, mark as active and bind OAuth provider
        if user.status != UserStatus.ACTIVE:
            user.status = UserStatus.ACTIVE
            await repository.commit()

        # Create session and redirect
        session_value = build_session_cookie_value(user)
        response = RedirectResponse(url="/workspace", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            key=settings.auth.session_cookie_name,
            value=session_value,
            httponly=True,
            max_age=settings.auth.session_ttl_seconds,
            samesite="lax",
            secure=settings.app.base_url.startswith("https://"),
            path="/",
        )
        response.delete_cookie("oauth_state", path="/")
        return response

    except Exception as exc:
        logger.exception("Google OAuth error")
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            _build_login_template_context(title="PitchCopyTrade", error=f"OAuth error: {str(exc)[:100]}"),
        )


@router.get("/auth/yandex", include_in_schema=False)
async def yandex_oauth_start(request: Request) -> Response:
    """X4.4: Redirect to Yandex OAuth consent screen."""
    from authlib.integrations.httpx_client import AsyncOAuth2Client

    settings = get_settings()
    if not settings.yandex_client_id or not settings.yandex_client_secret:
        raise HTTPException(status_code=404, detail="Yandex OAuth not configured")

    redirect_uri = f"{settings.app.base_url.rstrip('/')}/auth/yandex/callback"

    client = AsyncOAuth2Client(
        client_id=settings.yandex_client_id,
        client_secret=settings.yandex_client_secret.get_secret_value(),
        redirect_uri=redirect_uri,
    )

    uri, state = client.create_authorization_url(
        "https://oauth.yandex.ru/authorize",
    )

    response = RedirectResponse(url=uri, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        max_age=600,
        samesite="lax",
        secure=settings.app.base_url.startswith("https://"),
        path="/",
    )
    return response


@router.get("/auth/yandex/callback", response_class=HTMLResponse, include_in_schema=False)
async def yandex_oauth_callback(
    request: Request,
    code: str = None,
    state: str = None,
    repository: AuthRepository = Depends(get_auth_repository),
) -> Response:
    """X4.6: Handle Yandex OAuth callback."""
    from authlib.integrations.httpx_client import AsyncOAuth2Client
    import httpx

    settings = get_settings()
    if not settings.yandex_client_id or not settings.yandex_client_secret:
        raise HTTPException(status_code=404, detail="Yandex OAuth not configured")

    stored_state = request.cookies.get("oauth_state")
    if not state or state != stored_state:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            _build_login_template_context(title="PitchCopyTrade", error="OAuth validation failed"),
        )

    redirect_uri = f"{settings.app.base_url.rstrip('/')}/auth/yandex/callback"

    client = AsyncOAuth2Client(
        client_id=settings.yandex_client_id,
        client_secret=settings.yandex_client_secret.get_secret_value(),
        redirect_uri=redirect_uri,
    )

    try:
        # Exchange code for token
        token = await client.fetch_token("https://oauth.yandex.ru/token", code=code)

        # Get user info
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.get(
                "https://login.yandex.ru/info",
                headers={"Authorization": f"OAuth {token['access_token']}"},
            )
            user_info = resp.json()

        email = user_info.get("default_email")
        if not email:
            return templates.TemplateResponse(
                request,
                "auth/login.html",
                _build_login_template_context(title="PitchCopyTrade", error="Could not get email from Yandex"),
            )

        # X4.6: Find user by email in repository
        user = await repository.get_user_by_identity(email)
        if user is None:
            return templates.TemplateResponse(
                request,
                "auth/login.html",
                _build_login_template_context(title="PitchCopyTrade", error="Email not found in staff directory"),
            )

        # If inactive, mark as active
        if user.status != UserStatus.ACTIVE:
            user.status = UserStatus.ACTIVE
            await repository.save_user(user)

        # Create session and redirect
        session_value = build_session_cookie_value(user)
        response = RedirectResponse(url="/workspace", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            key=settings.auth.session_cookie_name,
            value=session_value,
            httponly=True,
            max_age=settings.auth.session_ttl_seconds,
            samesite="lax",
            secure=settings.app.base_url.startswith("https://"),
            path="/",
        )
        response.delete_cookie("oauth_state", path="/")
        return response

    except Exception as exc:
        logger.exception("Yandex OAuth error")
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            _build_login_template_context(title="PitchCopyTrade", error=f"OAuth error: {str(exc)[:100]}"),
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
        return "/app/catalog"
    # Y4: Normalize path and prevent open redirect attacks
    next_path = next_path.replace("\\", "/")
    if not next_path.startswith("/") or next_path.startswith("//"):
        return "/app/catalog"
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
    # X4.7: OAuth button visibility depends on credentials being configured
    return {
        "title": title,
        "error": error,
        "identity": identity,
        "invite_token": invite_token,
        "dev_bootstrap_enabled": settings.app.env.lower() in {"development", "local", "test"},
        "dev_bootstrap_url": f"{base_url}/dev/bootstrap",
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
        "google_oauth_enabled": bool(settings.google_client_id and settings.google_client_secret),
        "yandex_oauth_enabled": bool(settings.yandex_client_id and settings.yandex_client_secret),
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
